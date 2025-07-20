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

load_dotenv()

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

# Simple cache for function results (in production, use Redis or similar)
function_cache = {}

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
        
        if venues:
            logger.info(f"Found {len(venues)} venues. Remember to use resy_id field for availability checks.")
            if venues and len(venues) > 0:
                first_venue = venues[0]
                logger.info(f"First venue: name='{first_venue.get('name', 'N/A')}', resy_id='{first_venue.get('resy_id', 'N/A')}'")
        
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
    
    if not venue_id.isdigit():
        error_msg = f"Invalid venue_id: '{venue_id}'. Expected a numeric ID (resy_id) from search results, not a restaurant name."
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    
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
    
    if not venue_id.isdigit():
        error_msg = f"Invalid venue_id: '{venue_id}'. Expected a numeric ID (resy_id) from search results, not a restaurant name."
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    
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

async def get_user_reservations_tool(only_open_reservations: bool = True) -> Dict[str, Any]:
    """Get all reservations for the user either open or closed or all."""
    logger.info("Fetching all reservations")
    
    try:
        reservations = await asyncio.to_thread(get_all_reservations, only_open_reservations)
        
        return {
            "reservations": reservations,
            "count": len(reservations),
            "retrieved_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching reservations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch reservations: {str(e)}")


AVAILABLE_FUNCTIONS = {
    "search_restaurants": search_restaurants_tool,
    "check_availability": check_availability_tool,
    "get_time_slots": get_time_slots_tool,
    "get_user_reservations_tool": get_user_reservations_tool,
}

FUNCTION_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": "Search for restaurants and venues using semantic similarity. Use descriptive terms like 'Italian restaurants', 'romantic date spots', 'casual lunch places', etc. Each result includes a 'resy_id' field that must be used for subsequent availability checks.",
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
            "description": "Check available dates for a specific venue. Use this after finding a restaurant to see when they have availability. IMPORTANT: Use the 'resy_id' field from search results as the venue_id parameter, not the restaurant name. Workflow: 1) Search for restaurant, 2) Extract resy_id from results, 3) Use resy_id as venue_id here.",
            "parameters": {
                "type": "object",
                "properties": {
                    "venue_id": {
                        "type": "string",
                        "description": "The Resy venue ID (resy_id) from search results. This should be a numeric string like '12345', not the restaurant name. Must be extracted from previous search_restaurants results."
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
            "description": "Get available time slots and booking tokens for a specific date and venue. Use this to see specific available times after checking general availability. IMPORTANT: Use the 'resy_id' field from search results as the venue_id parameter, not the restaurant name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "venue_id": {
                        "type": "string",
                        "description": "The Resy venue ID (resy_id) from search results. This should be a numeric string like '12345', not the restaurant name."
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
            "name": "get_user_reservations_tool",
            "description": "Get all reservations for the user or just current (upcoming) reservations based on user preference. Use this to see what reservations are already booked or have been booked in the past.",
            "parameters": {
                "type": "object",
                "properties": {
                    "only_open_reservations": {
                        "type": "boolean",
                        "description": "Whether to only return open (future) reservations (default: True)",
                        "default": True
                    }
                },
                "required": ["only_open_reservations"]
            }
        }
    }
]

# Add this after the imports
class RestaurantContext:
    def __init__(self):
        self.identified_restaurants = {}  # name -> {resy_id, name, type, neighborhood, etc.}
    
    def add_restaurant(self, name: str, resy_id: str, **details):
        """Add a restaurant to the context."""
        self.identified_restaurants[name.lower()] = {
            "resy_id": resy_id,
            "name": name,
            **details
        }
    
    def get_restaurant(self, name: str):
        """Get restaurant info by name."""
        return self.identified_restaurants.get(name.lower())
    
    def get_context_summary(self):
        """Get a summary of identified restaurants for the AI."""
        if not self.identified_restaurants:
            return ""
        
        summary = "\n\nPREVIOUSLY IDENTIFIED RESTAURANTS:\n"
        for name, info in self.identified_restaurants.items():
            summary += f"- {info['name']} (resy_id: {info['resy_id']}, type: {info.get('type', 'N/A')}, neighborhood: {info.get('neighborhood', 'N/A')})\n"
        return summary

# Add this as a global variable
restaurant_context = RestaurantContext()

# API Endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_assistant(request: ChatRequest):
    """Chat with the reservation assistant using OpenAI function calling."""
    
    if not openai_client.api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    try:
        # Get context summary for previously identified restaurants
        context_summary = restaurant_context.get_context_summary()
        
        messages = [
            {
                "role": "system",
                "content": f"""You are a friendly restaurant reservation assistant with access to tools to help the user book a restaurant.

Your job is to find out all the details about a users reservation preference, and then use those tools to book a restaurant.

TYPICAL WORKFLOWS:
1. User asks about a restaurant → search_restaurants() to find relevant restaurants and then check_availability() for each if needed
2. User asks for availability → search_restaurants() → check_availability() → get_time_slots()
3. User asks for times → search_restaurants() → check_availability() → get_time_slots()

CRITICAL RULES:
- Always use resy_id from search results, never restaurant names
- If you search and find venues, automatically check availability for the most relevant ones
- If you check availability and find dates, offer to get specific times
- Show key details: name, type, neighborhood, rating
- Explain booking tokens are for Resy booking

CONTEXT AWARENESS:
- If the user mentions a restaurant that's already been identified, use its resy_id directly
- DO NOT search again for restaurants that are already in the context
- Only search for new restaurants when the user asks about a restaurant not previously discussed{context_summary}

Example workflow:
User: "I want to book at Gertrudes"
1. search_restaurants("Gertrudes") 
2. Extract resy_id from results
3. check_availability(venue_id="12345", current_date="2024-01-15")
4. If dates available, get_time_slots(venue_id="12345", date="2024-01-15")

User: "What times are available for Gertrudes?" (after previous search)
1. Use Gertrudes resy_id from context
2. check_availability(venue_id="12345", current_date="2024-01-15") 
3. get_time_slots(venue_id="12345", date="2024-01-15")"""
            }
        ]

        max_history = 10 
        recent_history = request.conversation_history[-max_history:] if len(request.conversation_history) > max_history else request.conversation_history
        
        # Filter out any system messages from conversation history to avoid duplicates
        for msg in recent_history:
            if msg.role != "system":  # Only add non-system messages
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": request.message})

        # Multi-step workflow execution - one tool call at a time
        max_iterations = 5  # Prevent infinite loops
        iteration = 0
        all_function_calls = []
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Workflow iteration {iteration}")
            
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                tools=FUNCTION_DEFINITIONS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=800 
            )
            
            assistant_message = response.choices[0].message
            
            # If no tool calls, we're done
            if not assistant_message.tool_calls:
                break
            
            # Execute only the first tool call (one at a time)
            tool_call = assistant_message.tool_calls[0]
            if tool_call.type != "function":
                break
                
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            logger.info(f"Executing function: {function_name} with args: {function_args}")
    
            if function_name == "check_availability":
                logger.info(f"AVAILABILITY CHECK - venue_id: '{function_args.get('venue_id', 'NOT_FOUND')}' (type: {type(function_args.get('venue_id', 'NOT_FOUND'))})")
            elif function_name == "search_restaurants":
                logger.info(f"SEARCH REQUEST - query: '{function_args.get('query', 'NOT_FOUND')}'")
            
            if function_name in AVAILABLE_FUNCTIONS:
                try:
                    # Check cache for search results (cache for 5 minutes)
                    cache_key = f"{function_name}:{json.dumps(function_args, sort_keys=True)}"
                    current_time = datetime.now().timestamp()
                    
                    if function_name == "search_restaurants" and cache_key in function_cache:
                        cache_entry = function_cache[cache_key]
                        if current_time - cache_entry["timestamp"] < 300:  # 5 minutes
                            logger.info(f"Using cached result for {function_name}")
                            function_result = cache_entry["result"]
                        else:
                            # Cache expired, remove it
                            del function_cache[cache_key]
                            function_result = await AVAILABLE_FUNCTIONS[function_name](**function_args)
                            function_cache[cache_key] = {"result": function_result, "timestamp": current_time}
                    else:
                        function_result = await AVAILABLE_FUNCTIONS[function_name](**function_args)
                        if function_name == "search_restaurants":
                            function_cache[cache_key] = {"result": function_result, "timestamp": current_time}
                    
                    all_function_calls.append({
                        "name": function_name,
                        "arguments": function_args,
                        "result": function_result
                    })
                    
                    # Add the assistant message with tool call
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call.dict()]
                    })

                    # Add the tool result
                    result_content = json.dumps(function_result)
                    if len(result_content) > 2000: 
                        truncated_result = function_result.copy()
                        if 'venues' in truncated_result and len(truncated_result['venues']) > 3:
                            truncated_result['venues'] = truncated_result['venues'][:3]
                            truncated_result['count'] = len(truncated_result['venues'])
                            truncated_result['_truncated'] = True
                        result_content = json.dumps(truncated_result)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_content
                    })
                    
                    logger.info(f"Completed function {function_name}, continuing workflow...")
                    
                    # In the function execution loop, add this after successful search_restaurants calls:
                    if function_name == "search_restaurants" and function_result.get("venues"):
                        # Store restaurant information in context
                        for venue in function_result["venues"]:
                            restaurant_context.add_restaurant(
                                name=venue["name"],
                                resy_id=venue["resy_id"],
                                type=venue.get("type", ""),
                                neighborhood=venue.get("neighborhood", ""),
                                rating=venue.get("rating", 0)
                            )

                except Exception as e:
                    logger.error(f"Error calling function {function_name}: {str(e)}")
                    all_function_calls.append({
                        "name": function_name,
                        "arguments": function_args,
                        "result": {"error": str(e)}
                    })
                    # Add error to messages and break
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": str(e)})
                    })
                    break
            else:
                logger.warning(f"Unknown function: {function_name}")
                break
        
        # Generate final response
        final_response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        return ChatResponse(
            message=final_response.choices[0].message.content,
            function_calls=all_function_calls
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
    return await get_user_reservations_tool(only_open_reservations=True)

@app.get("/api/all-reservations")
async def get_all_reservations_endpoint():
    """Direct endpoint to get all reservations (current and past)."""
    return await get_user_reservations_tool(only_open_reservations=False)

@app.post("/api/reset-context")
async def reset_context():
    """Reset the restaurant context and clear all stored restaurant information."""
    global restaurant_context
    restaurant_context = RestaurantContext()
    logger.info("Restaurant context reset")
    return {"status": "success", "message": "Context reset successfully"}

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