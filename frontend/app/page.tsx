'use client'

import React, { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Calendar, MapPin, Clock, Star } from 'lucide-react'
import axios from 'axios'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  functionCalls?: FunctionCall[]
}

interface FunctionCall {
  name: string
  arguments: any
  result: any
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'Hello! I\'m your restaurant reservation assistant. I can help you find restaurants, check availability, and get booking information. What would you like to do today?',
      timestamp: new Date()
    }
  ])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return

    const userMessage: ChatMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setIsLoading(true)

    try {
      const response = await axios.post(`${API_BASE}/api/chat`, {
        message: inputMessage,
        conversation_history: messages.map(msg => ({
          role: msg.role,
          content: msg.content
        }))
      })

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.data.message,
        timestamp: new Date(),
        functionCalls: response.data.function_calls || []
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const renderFunctionResult = (functionCall: FunctionCall) => {
    const { name, result } = functionCall

    if (result.error) {
      return (
        <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-700 text-sm">Error: {result.error}</p>
        </div>
      )
    }

    switch (name) {
      case 'search_restaurants':
        return (
          <div className="mt-3 space-y-3">
            <p className="text-sm font-medium text-gray-700">Found {result.count} restaurants:</p>
            {result.venues?.slice(0, 3).map((venue: any, index: number) => (
              <div key={index} className="p-3 bg-white border border-gray-200 rounded-lg">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900">{venue.name}</h3>
                    <p className="text-sm text-gray-600">{venue.type}</p>
                    <div className="flex items-center mt-1 space-x-2">
                      <MapPin className="w-3 h-3 text-gray-400" />
                      <span className="text-xs text-gray-500">{venue.neighborhood}</span>
                    </div>
                    {venue.description && (
                      <p className="mt-2 text-sm text-gray-600">{venue.description}</p>
                    )}
                  </div>
                  {venue.rating > 0 && (
                    <div className="flex items-center ml-3">
                      <Star className="w-4 h-4 text-yellow-400 fill-current" />
                      <span className="ml-1 text-sm font-medium">{venue.rating}</span>
                    </div>
                  )}
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  Venue ID: {venue.resy_id}
                </div>
              </div>
            ))}
          </div>
        )

      case 'check_availability':
        return (
          <div className="mt-3">
            <p className="text-sm font-medium text-gray-700 mb-2">
              Available dates (for {result.requested_seats} seats):
            </p>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              {result.available_dates?.length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {result.available_dates.slice(0, 6).map((date: string, index: number) => (
                    <div key={index} className="flex items-center p-2 bg-green-50 rounded text-sm">
                      <Calendar className="w-3 h-3 text-green-600 mr-1" />
                      {new Date(date).toLocaleDateString()}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No availability found</p>
              )}
            </div>
          </div>
        )

      case 'get_time_slots':
        return (
          <div className="mt-3">
            <p className="text-sm font-medium text-gray-700 mb-2">
              Available time slots for {result.date}:
            </p>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              {Object.keys(result.available_slots || {}).length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {Object.entries(result.available_slots).slice(0, 8).map(([time, data]: [string, any], index: number) => (
                    <div key={index} className="flex items-center p-2 bg-blue-50 rounded text-sm">
                      <Clock className="w-3 h-3 text-blue-600 mr-1" />
                      {time}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No time slots available</p>
              )}
            </div>
          </div>
        )

      case 'get_current_reservations':
        return (
          <div className="mt-3">
            <p className="text-sm font-medium text-gray-700 mb-2">
              Current reservations ({result.count}):
            </p>
            <div className="space-y-2">
              {result.reservations?.slice(0, 3).map((reservation: any, index: number) => (
                <div key={index} className="p-3 bg-white border border-gray-200 rounded-lg">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">
                        {reservation.venue?.name || 'Restaurant'}
                      </h3>
                      <p className="text-sm text-gray-600">
                        {reservation.date?.start ? new Date(reservation.date.start).toLocaleString() : 'Date TBD'}
                      </p>
                      <p className="text-xs text-gray-500">
                        Party of {reservation.party_size || 'N/A'}
                      </p>
                    </div>
                  </div>
                </div>
              )) || <p className="text-gray-500 text-sm">No reservations found</p>}
            </div>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4 shadow-sm">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <Bot className="w-6 h-6 text-blue-600" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Restaurant Assistant</h1>
            <p className="text-sm text-gray-500">Find restaurants, check availability, and manage reservations</p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`chat-message ${message.role}`}>
              <div className="flex items-start space-x-2">
                <div className={`p-1 rounded-full ${
                  message.role === 'user' ? 'bg-blue-700' : 'bg-gray-300'
                }`}>
                  {message.role === 'user' ? (
                    <User className="w-4 h-4 text-white" />
                  ) : (
                    <Bot className="w-4 h-4 text-gray-700" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {message.functionCalls && message.functionCalls.map((functionCall, fcIndex) => (
                    <div key={fcIndex}>
                      {renderFunctionResult(functionCall)}
                    </div>
                  ))}
                  <p className="text-xs mt-2 opacity-70">
                    {message.timestamp.toLocaleTimeString()}
                  </p>
                </div>
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="chat-message assistant">
              <div className="flex items-center space-x-2">
                <div className="p-1 rounded-full bg-gray-300">
                  <Bot className="w-4 h-4 text-gray-700" />
                </div>
                <div className="loading-dots">
                  <div></div>
                  <div></div>
                  <div></div>
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4 bg-white">
        <div className="flex space-x-2">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask me about restaurants, availability, or your reservations..."
            className="flex-1 p-3 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows={2}
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={isLoading || !inputMessage.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  )
} 