# Trip Planner - Restaurant Reservation Assistant

An AI-powered restaurant reservation assistant that helps you find restaurants, check availability, and manage bookings through a modern chat interface.

## Features

- 🔍 **Semantic Restaurant Search**: Find restaurants using natural language queries like "Italian restaurants with outdoor seating" or "romantic date night spots"
- 📅 **Availability Checking**: Check available dates for specific venues
- ⏰ **Time Slot Booking**: Get available time slots and booking tokens
- 📱 **Modern Chat Interface**: Clean, responsive web interface with real-time chat
- 🤖 **AI-Powered**: Uses OpenAI's GPT-4 with function calling to orchestrate restaurant tools

## Architecture

- **Backend**: FastAPI web server that wraps MCP (Model Context Protocol) tools
- **Frontend**: Next.js 14 with TypeScript and Tailwind CSS
- **AI**: OpenAI GPT-4 with function calling for tool orchestration
- **Database**: ChromaDB vector database for semantic restaurant search

## Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- OpenAI API key
- Resy API credentials

### Backend Setup

1. **Navigate to the backend directory**:
```bash
cd backend
```

2. **Install dependencies using Poetry**:
```bash
poetry install
```

3. **Set up environment variables**:
Create a `.env` file in the backend directory:
```bash
# OpenAI API Key (required for chat functionality)
OPENAI_API_KEY=your_openai_api_key_here

# Resy API Credentials (required for restaurant data)
RESY_API_KEY=your_resy_api_key
X_RESY_AUTH_TOKEN=your_resy_auth_token
```

4. **Start the backend server**:
```bash
poetry run python web_server.py
```

The API server will start on `http://localhost:8000`

### Frontend Setup

1. **Navigate to the frontend directory**:
```bash
cd frontend
```

2. **Install dependencies**:
```bash
npm install
```

3. **Start the development server**:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Usage

### Chat Interface

Once both servers are running, visit `http://localhost:3000` to access the chat interface.

Example conversations:

**Finding Restaurants**:
- "Find me Italian restaurants in Manhattan"
- "Show me romantic date night spots with good ratings"
- "I want a casual lunch place with outdoor seating"

**Checking Availability**:
- "Check availability for [restaurant] next week for 2 people"
- "What dates are available at venue ID 12345?"

**Getting Time Slots**:
- "Show me available times for [restaurant] on December 15th"
- "What time slots are open for 4 people on Friday?"

**Managing Reservations**:
- "Show me my current reservations"
- "What bookings do I have coming up?"

### Direct API Access

The backend also provides direct API endpoints for testing:

- **Health Check**: `GET http://localhost:8000/api/health`
- **Search Restaurants**: `POST http://localhost:8000/api/search-restaurants`
- **Check Availability**: `POST http://localhost:8000/api/check-availability`
- **Get Time Slots**: `POST http://localhost:8000/api/get-time-slots`
- **Current Reservations**: `GET http://localhost:8000/api/current-reservations`

API documentation is available at `http://localhost:8000/docs`

## Development

### Running Both Servers

You can run both servers simultaneously:

**Terminal 1 (Backend)**:
```bash
cd backend
poetry run python web_server.py
```

**Terminal 2 (Frontend)**:
```bash
cd frontend
npm run dev
```

### MCP Server (Optional)

The original MCP server is also available for Claude Desktop integration:

```bash
cd backend
poetry run python mcp_server.py
```

### Project Structure

```
trip-planner/
├── backend/
│   ├── mcp_server.py          # Original MCP server
│   ├── web_server.py          # FastAPI web server  
│   ├── reservation_tools.py   # Core reservation logic
│   └── pyproject.toml         # Python dependencies
├── frontend/
│   ├── app/
│   │   ├── page.tsx           # Main chat interface
│   │   ├── layout.tsx         # App layout
│   │   └── globals.css        # Tailwind styles
│   └── package.json           # Node dependencies
└── venue_vector_db/           # ChromaDB vector store
```

## Customization

### Adding New Tools

To add new reservation tools:

1. Add the function to `reservation_tools.py`
2. Create a wrapper in `web_server.py` 
3. Add to `AVAILABLE_FUNCTIONS` and `FUNCTION_DEFINITIONS`
4. Update the frontend UI to handle the new tool results

### Styling

The frontend uses Tailwind CSS. Customize the chat interface by editing:
- `frontend/app/globals.css` - Global styles and chat message styles
- `frontend/app/page.tsx` - Component styles and layout
- `frontend/tailwind.config.js` - Tailwind configuration

## Troubleshooting

### Common Issues

**"OpenAI API key not configured"**:
- Make sure `OPENAI_API_KEY` is set in your backend `.env` file

**"Failed to search venues"**:
- Check that your Resy API credentials are correctly set
- Ensure the vector database is populated (run `create_venue_vector_store.py`)

**Frontend can't connect to backend**:
- Verify the backend is running on port 8000
- Check CORS settings in `web_server.py` if accessing from different origins

**Chat responses are slow**:
- This is normal for the first request as models load
- Subsequent requests should be faster

## License

This project is for educational and personal use. Please respect Resy's terms of service when using their API. 