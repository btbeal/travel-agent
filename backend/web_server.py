import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
from dotenv import load_dotenv

from reservation_tools import (
    get_all_reservations,
    search_venues,
    get_available_dates,
    get_timeslots_and_associated_booking_tokens,
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Trip Planner Reservation API",
    description="API for restaurant reservations and booking assistance",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Request/Response Models
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_history: List[ChatMessage] = []

class ChatResponse(BaseModel):
    message: str
    function_calls: List[Dict[str, Any]] = []

class VenueSearchRequest(BaseModel):
    query: str
    n_results: int = 5
    filter_dict: Optional[Dict[str, Any]] = None

class DateRequest(BaseModel):
    venue_id: str
    current_date: str
    num_seats: int = 2

class TimeslotRequest(BaseModel):
    venue_id: str
    date: str
    num_seats: int = 2
    lat: float = 0.0
    long: float = 0.0

# Tool functions that match the MCP server
async def search_restaurants_tool(query: str, n_results: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Search for restaurants and venues using semantic similarity."""
    logger.info(f"Searching venues with query: '{query}'")
    
    try:
        results = await asyncio.to_thread(search_venues, query, n_results, filter_dict)
        
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
            "query": query,
            "venues": venues,
            "count": len(venues),
            "searched_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error searching venues: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search venues: {str(e)}")

async def check_availability_tool(venue_id: str, current_date: str, num_seats: int = 2) -> Dict[str, Any]:
    """Check available dates for a specific venue."""
    logger.info(f"Checking availability for venue {venue_id} starting {current_date}")
    
    try:
        available_dates = await asyncio.to_thread(get_available_dates, venue_id, current_date, num_seats)
        
        return {
            "venue_id": venue_id,
            "requested_seats": num_seats,
            "search_start_date": current_date,
            "available_dates": available_dates,
            "count": len(available_dates),
            "checked_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check availability: {str(e)}")

async def get_time_slots_tool(venue_id: str, date: str, num_seats: int = 2, lat: float = 0.0, long: float = 0.0) -> Dict[str, Any]:
    """Get available time slots and booking tokens for a specific date and venue."""
    logger.info(f"Getting time slots for venue {venue_id} on {date}")
    
    try:
        timeslots = await asyncio.to_thread(
            get_timeslots_and_associated_booking_tokens,
            venue_id, date, num_seats, lat, long
        )
        
        formatted_slots = {}
        for timestamp, booking_token in timeslots.items():
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%I:%M %p')
                formatted_slots[formatted_time] = {
                    "booking_token": booking_token,
                    "original_timestamp": timestamp
                }
            except:
                formatted_slots[timestamp] = {
                    "booking_token": booking_token,
                    "original_timestamp": timestamp
                }
        
        return {
            "venue_id": venue_id,
            "date": date,
            "requested_seats": num_seats,
            "available_slots": formatted_slots,
            "slot_count": len(formatted_slots),
            "retrieved_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting time slots: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get time slots: {str(e)}")

async def get_current_reservations_tool() -> Dict[str, Any]:
    """Get all current (open) reservations for the user."""
    logger.info("Fetching current reservations")
    
    try:
        reservations = await asyncio.to_thread(get_all_reservations, only_open_reservations=True)
        
        return {
            "reservations": reservations,
            "count": len(reservations),
            "retrieved_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching reservations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch reservations: {str(e)}")

# OpenAI function definitions
AVAILABLE_FUNCTIONS = {
    "search_restaurants": search_restaurants_tool,
    "check_availability": check_availability_tool,
    "get_time_slots": get_time_slots_tool,
    "get_current_reservations": get_current_reservations_tool,
}

FUNCTION_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": "Search for restaurants and venues using semantic similarity. Use descriptive terms like 'Italian restaurants', 'romantic date spots', 'casual lunch places', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Plain text query to search for restaurant venues"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    },
                    "filter_dict": {
                        "type": "object",
                        "description": "Optional filter for venues by metadata",
                        "properties": {}
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available dates for a specific venue. Use this after finding a restaurant to see when they have availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "venue_id": {
                        "type": "string",
                        "description": "The Resy venue ID from search results"
                    },
                    "current_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "num_seats": {
                        "type": "integer",
                        "description": "Number of seats needed (default: 2)",
                        "default": 2
                    }
                },
                "required": ["venue_id", "current_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time_slots",
            "description": "Get available time slots and booking tokens for a specific date and venue. Use this to see specific available times after checking general availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "venue_id": {
                        "type": "string",
                        "description": "The Resy venue ID"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format"
                    },
                    "num_seats": {
                        "type": "integer",
                        "description": "Number of seats needed (default: 2)",
                        "default": 2
                    },
                    "lat": {
                        "type": "number",
                        "description": "Latitude for the venue location (default: 0.0)",
                        "default": 0.0
                    },
                    "long": {
                        "type": "number", 
                        "description": "Longitude for the venue location (default: 0.0)",
                        "default": 0.0
                    }
                },
                "required": ["venue_id", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_reservations",
            "description": "Get all current (upcoming) reservations for the user. Use this to see what reservations are already booked.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

# API Endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_assistant(request: ChatRequest):
    """Chat with the reservation assistant using OpenAI function calling."""
    
    if not openai_client.api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    try:
        # Build conversation history
        messages = [
            {
                "role": "system",
                "content": """You are a helpful restaurant reservation assistant. You can help users:
1. Search for restaurants based on cuisine, location, occasion, etc.
2. Check availability for specific venues
3. Get available time slots for booking
4. View their current reservations

Always be helpful and provide clear, actionable information. When showing restaurant options, include key details like name, type, neighborhood, and rating. When showing availability, present dates and times in a user-friendly format.

If a user asks about booking, explain that you can show available time slots and booking tokens, but the actual booking would need to be completed through Resy or the restaurant directly."""
            }
        ]
        
        # Add conversation history
        for msg in request.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
        
        # Add the new user message
        messages.append({"role": "user", "content": request.message})
        
        # Call OpenAI with function calling
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=FUNCTION_DEFINITIONS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=1000
        )
        
        assistant_message = response.choices[0].message
        function_calls = []
        
        # Handle function calls if any
        if assistant_message.tool_calls:
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Calling function: {function_name} with args: {function_args}")
                
                if function_name in AVAILABLE_FUNCTIONS:
                    try:
                        # Call the function
                        function_result = await AVAILABLE_FUNCTIONS[function_name](**function_args)
                        function_calls.append({
                            "name": function_name,
                            "arguments": function_args,
                            "result": function_result
                        })
                        
                        # Add function result to conversation for final response
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [tool_call.dict()]
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(function_result)
                        })
                        
                    except Exception as e:
                        logger.error(f"Error calling function {function_name}: {str(e)}")
                        function_calls.append({
                            "name": function_name,
                            "arguments": function_args,
                            "result": {"error": str(e)}
                        })
            
            # Get final response after function calls
            final_response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            return ChatResponse(
                message=final_response.choices[0].message.content,
                function_calls=function_calls
            )
        
        else:
            # No function calls, return the assistant's message directly
            return ChatResponse(
                message=assistant_message.content or "I'm here to help with restaurant reservations!",
                function_calls=[]
            )
            
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

# Direct API endpoints (for testing)
@app.post("/api/search-restaurants")
async def search_restaurants_endpoint(request: VenueSearchRequest):
    """Direct endpoint to search for restaurants."""
    return await search_restaurants_tool(request.query, request.n_results, request.filter_dict)

@app.post("/api/check-availability") 
async def check_availability_endpoint(request: DateRequest):
    """Direct endpoint to check venue availability."""
    return await check_availability_tool(request.venue_id, request.current_date, request.num_seats)

@app.post("/api/get-time-slots")
async def get_time_slots_endpoint(request: TimeslotRequest):
    """Direct endpoint to get time slots."""
    return await get_time_slots_tool(request.venue_id, request.date, request.num_seats, request.lat, request.long)

@app.get("/api/current-reservations")
async def get_current_reservations_endpoint():
    """Direct endpoint to get current reservations."""
    return await get_current_reservations_tool()

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    print("Starting Trip Planner Web Server...")
    print("Frontend will be available at: http://localhost:3000")
    print("API documentation: http://localhost:8000/docs")
    print("Make sure to set OPENAI_API_KEY in your .env file")
    uvicorn.run("web_server:app", host="0.0.0.0", port=8000, reload=True) 