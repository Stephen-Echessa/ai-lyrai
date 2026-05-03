from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import pprint
import json
from agent import graph
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Add CORS middleware to allow connections from the Next.js app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://lyrai.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            song_url = message_data.get("song_url", "")
            guest_id = message_data.get("guest_id", "anonymous")

            print("Guest ID:", guest_id)
            
            # Add thread ID for memory checkpointing based on song URL
            config = {"configurable": {"thread_id": f"{guest_id}:{song_url}"}}

            # Run the graph asynchronously
            result = await graph.ainvoke(input={
                "messages": [HumanMessage(content=user_message)],
                "song_url": song_url
            }, config=config)

            # Get the AI response
            ai_response = result["messages"][-1].content[0]["text"]

            print("************************************************")
            print("\n New Messages \n")
            print("************************************************\n")

            for m in result["messages"]:
                m.pretty_print()

            # Send the response back
            await websocket.send_text(json.dumps({"response": ai_response}))

    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"Error: {e}")
        await websocket.send_text(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)