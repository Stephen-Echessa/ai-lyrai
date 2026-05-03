import os
import json
import asyncio
import aiosqlite
from dotenv import load_dotenv
from typing import Optional
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage, SystemMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.graph import StateGraph, MessagesState, START, END
from prompts import (
    MUSIC_ANALYSIS_PROMPT,
)
from tools import (
    spotify_track_metadata,
    genius_artist_profile,
    genius_song_lyrics,
    genius_song_description,
    _search_genius_for_spotify_track,
)

load_dotenv()

# Initialize Gemini LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7,
)

# llm = ChatNVIDIA(
#     api_key=os.environ.get("NVIDIA_API_KEY"), 
#     temperature=1,
#     top_p=0.95,
#     max_tokens=16384,
#     model_kwargs={"enable_thinking":False},
# )

# Define states
class AgentState(MessagesState):
    song_url: str
    song_data: Optional[dict] = None
    summary: Optional[str] = None


async def fetch_song_data(song_url: str) -> dict:
    # Extract song Spotify metadata if URL is provided
    spotify_metadata = spotify_track_metadata(song_url) if song_url else None
    song_title = spotify_metadata.get("name") if spotify_metadata else ""
    song_artist = spotify_metadata.get("artists", [None])[0] if spotify_metadata else ""
    print(f"Extracted Song Title: {song_title}, Artist: {song_artist}\n")

    # Extract song Genius metadata if Spotify metadata is available
    genius_metadata = _search_genius_for_spotify_track(song_title, song_artist) if song_title and song_artist else None
    if genius_metadata:
        artist_profile = genius_artist_profile(genius_metadata)
        song_lyrics = genius_song_lyrics(genius_metadata)
        song_description = genius_song_description(genius_metadata)

    return {
        "spotify_metadata": spotify_metadata,
        "artist_profile": artist_profile if genius_metadata else None,
        "song_lyrics": song_lyrics if genius_metadata else None,
        "song_description": song_description if genius_metadata else None,
    }


async def analysis_node(state: AgentState):
    messages = state["messages"]
    summary = state.get("summary", "No summary available yet.")
    song_url = state.get("song_url", None)

    if state.get("song_data") is None and song_url:
        try:
            data = await fetch_song_data(song_url)
            print("[agent debug] analysis_node -> fetched song data successfully\n")
            song_data = json.dumps(data, indent=2)
        except Exception as e:
            song_data = f"Unable to fetch song data: {str(e)}"

    else:
        song_data = state.get("song_data", None)
        print("[agent debug] analysis_node -> using existing song data from state\n")

    prompt = MUSIC_ANALYSIS_PROMPT.replace("{song_data}", song_data).replace("{summary}", summary)
    response = await llm.ainvoke([SystemMessage(content=prompt)] + messages)
    
    return {"messages": response, "song_data": song_data}


async def should_continue(state: AgentState):
    messages = state["messages"]

    if len(messages) > 6:
        return "summarize_conversation"
    
    return END
    

async def summarize_conversation(state: AgentState):
    summary = state.get("summary", None)
    if summary:
        summary_prompt = (
            f"This is a summary of the conversation to date: {summary}\n\n"
            "Extend the summary by taking into account the new messages above:"
        )
    else:
        summary_prompt = "Create a summary of the conversation above:"

    message = state["messages"] + [HumanMessage(content=summary_prompt)]
    response = await llm.ainvoke(message)

    # Delete all but the last 2 messages
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
    return {"summary": response.content[0]["text"], "messages": delete_messages}


conn = aiosqlite.connect(":memory:", check_same_thread=False)
checkpointer = AsyncSqliteSaver(conn)

builder = StateGraph(AgentState)

builder.add_node("analysis", analysis_node)
builder.add_node("summarize_conversation", summarize_conversation)

builder.add_edge(START, "analysis")
builder.add_conditional_edges("analysis", should_continue, ["summarize_conversation", END])
builder.add_edge("summarize_conversation", END)

graph = builder.compile(checkpointer=checkpointer)
