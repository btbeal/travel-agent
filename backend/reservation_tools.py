import json
import polars as pl
import requests
import yaml
import os
from typing import Dict
import chromadb
from dotenv import load_dotenv
from datetime import datetime, timedelta
load_dotenv()

API_KEY = os.getenv("RESY_API_KEY")
X_AUTH_TOKEN = os.getenv("X_RESY_AUTH_TOKEN")

def construct_token_key_header():
    auth_dict = {
        'X-Resy-Auth-Token': X_AUTH_TOKEN,
        'Authorization': f'ResyAPI api_key="{API_KEY}"',
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        'Origin': "https://widgets.resy.com",
        'Referer': "https://widgets.resy.com/"
    }
    return auth_dict


def get_all_reservations(only_open_reservations=True):
    """
    Get all reservations the user has made, which includes both open (future) and closed (past)reservations.
    The default filter is to only return open reservations.

    Args:
        only_open_reservations: Whether to only return open reservations
    Returns:
        A list of reservations for the user
    """
    response = requests.get(
        url='https://api.resy.com/3/user/reservations',
        headers=construct_token_key_header()
    )

    response_data_dict = json.loads(response.content)
    reservations = response_data_dict.get('reservations')

    if only_open_reservations:
        return [x for x in reservations if x.get('status', {}).get('finished', 0) != 1]

    return reservations

def get_all_venues():
    response = requests.get(
        url='https://api.resy.com/2/venues',
        headers=construct_token_key_header()
    )
    response_data_dict = json.loads(response.content)
    return response_data_dict

def search_venues(query: str, n_results: int = 2, filter_dict: Dict = None):
    """
    Search venues by semantic similarity and return the top n results. This returns helpful metadata that allows us 
    to conduct further inquiries such as assessing the availability for any of the restaurants that are returned.
    
    Note, that you can pre-filter by metadata
    using the filter_dict parameter as specified in the chromadb documentation: https://cookbook.chromadb.dev/core/filters/. 

    For example, to search only amongst venues in Williamsburg, New York, you can use the following:
    results = search_venues(
        "New American restaurants", 
        n_results=20,
        filter_dict={"$and": [{"neighborhood": {"$eq": "Williamsburg"}}, {"locality": {"$eq": "New York"}}]}
    )
    
    Note that this filtering can be very restrictive as many restaurants don't have the metadata fields filled out.

    Args:
        query: The query to search for
        n_results: The number of results to return
        filter_dict: A dictionary of metadata to filter by 
    Returns:
        The results of a chromadb query
    """
    client = chromadb.PersistentClient(path="../venue_vector_db")
    collection = client.get_collection(name="venues")

    return collection.query(
        query_texts=[query],
        n_results=n_results,
        where=filter_dict,
        include=['distances', 'metadatas', 'documents']
    )

def get_available_dates(venue_id: str, current_date: str, num_seats: int = 2):
    """
    Get a list of available dates for a given venue (with the resy id), which can then be used to identify available timeslots.

    Args:
        venue_id: The resy_id of the venue
        current_date: The current date for which to start the search for available dates
        num_seats: The number of seats to search for
    Returns:
        A list of dates for the given venue
    """
    end_date = datetime.strptime(current_date, '%Y-%m-%d') + timedelta(days=365)
    end_date = end_date.date()
    response = requests.get(
        url=f'https://api.resy.com/4/venue/calendar?venue_id={venue_id}&num_seats={num_seats}&start_date={current_date}&end_date={end_date}',
        headers=construct_token_key_header()
    )
    
    response_data_dict = json.loads(response.content)
    calendar_data = response_data_dict.get('scheduled')

    return [data.get('date') for data in calendar_data if data.get('inventory', {}).get('reservation', {}) == 'available']

def get_timeslots_and_associated_booking_tokens(venue_id: str, date: str, num_seats: int = 2, lat: float = 0, long: float = 0):
    """
    Get a dictionary of {timestamp: booking_token} for available timeslots at a given venue, which can then be used to present times to a user, and then book 
    with the booking token if a time is selected.

    Args:
        venue_id: The resy_id of the venue
        date: The date for which to search for available timeslots
        num_seats: The number of seats to search for
        lat: The latitude of the location gathered from the venue metadata
        long: The longitude of the location gathered from the venue metadata
    Returns:
        A dictionary of timestamp keys with booking tokens as values in the event that the user wants to book that given time slot.
    """
    url = f'https://api.resy.com/4/find?lat={lat}&long={long}&day={date}&party_size={num_seats}&venue_id={venue_id}'
    response = requests.get(
        url=url,
        headers=construct_token_key_header()
    )
    response_data_dict = json.loads(response.content)
    time_slots_metadata = response_data_dict.get('results').get('venues')[0].get('slots')
    time_metadata = {}
    for slot in time_slots_metadata:
        timestamp = slot.get('date').get('start')
        booking_token = slot.get('config').get('token')
        time_metadata[timestamp] = booking_token

    return time_metadata

