import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from reservation_tools import (
    get_all_reservations,
    search_venues,
    get_available_dates,
    get_timeslots_and_associated_booking_tokens,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Reservation Agent")

class VenueSearchRequest(BaseModel):
    query: str = Field(description="Plain text query to search for restaurant venues (e.g., 'Italian restaurants', 'steakhouse')")
    n_results: int = Field(default=5, description="Number of results to return")
    filter_dict: Optional[Dict[str, Any]] = Field(default=None, description="Optional filter for venues by metadata")

class DateRequest(BaseModel):
    venue_id: str = Field(description="The Resy venue ID")
    current_date: str = Field(description="Start date in YYYY-MM-DD format")
    num_seats: int = Field(default=2, description="Number of seats needed")

class TimeslotRequest(BaseModel):
    venue_id: str = Field(description="The Resy venue ID")
    date: str = Field(description="Date in YYYY-MM-DD format")
    num_seats: int = Field(default=2, description="Number of seats needed")
    lat: float = Field(default=0.0, description="Latitude for the venue location")
    long: float = Field(default=0.0, description="Longitude for the venue location")

class ReservationFilter(BaseModel):
    only_open: bool = Field(default=True, description="Whether to only return open (future) reservations")


@mcp.resource("reservations://current")
async def get_current_reservations() -> Dict[str, Any]:
    """Get all current (open) reservations for the user."""
    logger.info("Fetching current reservations")

    reservations = await asyncio.to_thread(get_all_reservations, only_open_reservations=True)
    
    return {
        "reservations": reservations,
        "count": len(reservations),
        "retrieved_at": datetime.now().isoformat()
    }

@mcp.resource("reservations://all")
async def get_all_user_reservations() -> Dict[str, Any]:
    """Get all reservations (both past and future) for the user."""
    logger.info("Fetching all reservations")
    
    reservations = await asyncio.to_thread(get_all_reservations, only_open_reservations=False)
    
    return {
        "reservations": reservations,
        "count": len(reservations),
        "retrieved_at": datetime.now().isoformat()
    }

# MCP Tools - Functions that can perform actions
@mcp.tool()
async def search_restaurants(request: VenueSearchRequest) -> Dict[str, Any]:
    """
    Search for restaurants and venues using semantic similarity.
    
    This tool allows you to find restaurants based on cuisine type, atmosphere, 
    location, or other descriptive terms. You can also filter by specific metadata
    like neighborhood or locality.
    
    Example queries:
    - "Italian restaurants with outdoor seating"
    - "Romantic date night spots"
    - "Casual lunch places"
    - "Steakhouses in Manhattan"
    """
    logger.info(f"Searching venues with query: '{request.query}'")
    
    try:
        # Run the search in a thread pool
        results = await asyncio.to_thread(
            search_venues,
            request.query,
            request.n_results,
            request.filter_dict
        )
        
        # Process results to make them more readable
        venues = []
        if results and 'metadatas' in results and results['metadatas']:
            for i, metadata in enumerate(results['metadatas'][0]):
                venue_info = {
                    "resy_id": str(metadata.get('resy_id', '')),
                    "name": metadata.get('name', ''),
                    "type": metadata.get('type', ''),
                    "description": metadata.get('description', ''),
                    "neighborhood": metadata.get('neighborhood', ''),
                    "locality": metadata.get('locality', ''),
                    "address": metadata.get('address', ''),
                    "rating": metadata.get('rating', 0),
                    "price_range_id": metadata.get('price_range_id', 0),
                    "latitude": metadata.get('latitude', 0),
                    "longitude": metadata.get('longitude', 0),
                    "distance_score": results['distances'][0][i] if results.get('distances') else None
                }
                venues.append(venue_info)
        
        return {
            "query": request.query,
            "venues": venues,
            "count": len(venues),
            "searched_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error searching venues: {str(e)}")
        raise ValueError(f"Failed to search venues: {str(e)}")

@mcp.tool()
async def check_availability(request: DateRequest) -> Dict[str, Any]:
    """
    Check available dates for a specific venue.
    
    This tool returns all available dates for a given restaurant within the next year.
    Use this after finding a restaurant you're interested in to see when they have availability.
    """
    logger.info(f"Checking availability for venue {request.venue_id} starting {request.current_date}")
    
    try:
        available_dates = await asyncio.to_thread(
            get_available_dates,
            request.venue_id,
            request.current_date,
            request.num_seats
        )
        
        return {
            "venue_id": request.venue_id,
            "requested_seats": request.num_seats,
            "search_start_date": request.current_date,
            "available_dates": available_dates,
            "count": len(available_dates),
            "checked_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        raise ValueError(f"Failed to check availability: {str(e)}")

@mcp.tool()
async def get_time_slots(request: TimeslotRequest) -> Dict[str, Any]:
    """
    Get available time slots and booking tokens for a specific date and venue.
    
    This tool returns all available time slots for a specific date, along with the
    booking tokens needed to make a reservation. Use this after checking availability
    to see specific times and get the tokens needed for booking.
    """
    logger.info(f"Getting time slots for venue {request.venue_id} on {request.date}")
    
    try:
        timeslots = await asyncio.to_thread(
            get_timeslots_and_associated_booking_tokens,
            request.venue_id,
            request.date,
            request.num_seats,
            request.lat,
            request.long
        )
        
        # Convert the timestamp keys to more readable format
        formatted_slots = {}
        for timestamp, booking_token in timeslots.items():
            try:
                # Parse the timestamp and format it nicely
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%I:%M %p')
                formatted_slots[formatted_time] = {
                    "booking_token": booking_token,
                    "original_timestamp": timestamp
                }
            except:
                # If parsing fails, use original timestamp
                formatted_slots[timestamp] = {
                    "booking_token": booking_token,
                    "original_timestamp": timestamp
                }
        
        return {
            "venue_id": request.venue_id,
            "date": request.date,
            "requested_seats": request.num_seats,
            "available_slots": formatted_slots,
            "slot_count": len(formatted_slots),
            "retrieved_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting time slots: {str(e)}")
        raise ValueError(f"Failed to get time slots: {str(e)}")

@mcp.tool()
async def get_reservation_summary() -> Dict[str, Any]:
    """
    Get a summary of the user's reservation status.
    
    This tool provides a quick overview of upcoming reservations, including
    counts and basic details.
    """
    logger.info("Generating reservation summary")
    
    try:
        # Get both open and all reservations for summary
        open_reservations = await asyncio.to_thread(get_all_reservations, only_open_reservations=True)
        all_reservations = await asyncio.to_thread(get_all_reservations, only_open_reservations=False)
        
        # Basic statistics
        total_count = len(all_reservations)
        upcoming_count = len(open_reservations)
        past_count = total_count - upcoming_count
        
        # Get next reservation if available
        next_reservation = None
        if open_reservations:
            # Sort by date to find the next one
            try:
                sorted_reservations = sorted(
                    open_reservations,
                    key=lambda x: x.get('date', {}).get('start', '')
                )
                next_reservation = sorted_reservations[0] if sorted_reservations else None
            except:
                next_reservation = open_reservations[0]
        
        return {
            "total_reservations": total_count,
            "upcoming_reservations": upcoming_count,
            "past_reservations": past_count,
            "next_reservation": next_reservation,
            "summary_generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating reservation summary: {str(e)}")
        raise ValueError(f"Failed to generate reservation summary: {str(e)}")

# MCP Prompts - Templates for consistent interactions
@mcp.prompt()
async def restaurant_recommendation_prompt(
    cuisine_type: str,
    occasion: str = "casual dining",
    location: str = "anywhere",
    party_size: int = 2
) -> str:
    """
    Generate a prompt for restaurant recommendations based on user preferences.
    
    This prompt helps structure requests for restaurant suggestions with specific
    criteria and context.
    """
    return f"""
You are a knowledgeable restaurant reservation assistant. Help find the perfect restaurant based on these preferences:

**Dining Preferences:**
- Cuisine Type: {cuisine_type}
- Occasion: {occasion}
- Location: {location}
- Party Size: {party_size} people

**Your Task:**
1. Search for restaurants that match these criteria
2. Consider factors like atmosphere, price range, and reviews
3. Provide 3-5 top recommendations with explanations
4. For each recommendation, include:
   - Restaurant name and type
   - Why it's a good fit for the occasion
   - Location and neighborhood
   - Any special features or highlights

**Search Strategy:**
- Use descriptive search terms that combine cuisine and occasion
- Consider location filters if specific area mentioned
- Look for restaurants with good ratings and appropriate price range

Please search for restaurants and provide thoughtful recommendations based on the criteria above.
"""

@mcp.prompt()
async def booking_assistance_prompt(
    restaurant_name: str,
    preferred_date: str,
    preferred_time: str = "evening",
    party_size: int = 2
) -> str:
    """
    Generate a prompt for booking assistance at a specific restaurant.
    """
    return f"""
You are helping to make a reservation at {restaurant_name}. Here are the booking details:

**Reservation Details:**
- Restaurant: {restaurant_name}
- Preferred Date: {preferred_date}
- Preferred Time: {preferred_time}
- Party Size: {party_size} people

**Your Task:**
1. Check availability for the requested date
2. Show available time slots
3. Help select the best time based on preferences
4. Provide booking tokens for the chosen time slot

**Booking Process:**
1. First, check what dates are available around the preferred date
2. Once a suitable date is found, get the specific time slots
3. Present the options clearly with times in readable format
4. Explain how to proceed with the actual booking

Please help find and present the best available options for this reservation.
"""

def main():
    """Main entry point for the MCP server."""
    print("🍽️  Starting Reservation Agent MCP Server...")
    print("📋 Available Resources:")
    print("   - reservations://current - Get current reservations")
    print("   - reservations://all - Get all reservations")
    print("🔧 Available Tools:")
    print("   - search_restaurants - Search for restaurants and venues")
    print("   - check_availability - Check available dates for a venue")
    print("   - get_time_slots - Get available time slots and booking tokens")
    print("   - get_reservation_summary - Get reservation status summary")
    print("📝 Available Prompts:")
    print("   - restaurant_recommendation_prompt - Generate restaurant search prompts")
    print("   - booking_assistance_prompt - Generate booking assistance prompts")
    print("\n✅ Server ready for connections!")
    print("💡 Make sure your .env file contains RESY_API_KEY and X_RESY_AUTH_TOKEN")

    # Run the server
    mcp.run()

if __name__ == "__main__":
    main() 