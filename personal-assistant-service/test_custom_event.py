import asyncio
from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.runnables import RunnableLambda

async def handle_auth_url(auth_url):
    print("handle_auth_url: Dispatching event...")
    await adispatch_custom_event("auth_required", {"auth_url": auth_url})
    print("handle_auth_url: Dispatched.")

async def sdk_wrapper(callback):
    print("SDK: calling callback...")
    await callback("https://example.com")
    print("SDK: callback returned, sleeping 3 seconds (polling)...")
    await asyncio.sleep(3)
    print("SDK: polling done.")

async def slow_auth_tool(x):
    await sdk_wrapper(handle_auth_url)
    return "Auth successful"

async def main():
    runnable = RunnableLambda(slow_auth_tool)
    
    async for event in runnable.astream_events("do it", version="v2"):
        kind = event["event"]
        name = event.get("name")
        if kind == "on_custom_event":
            print(f"!!! GOT CUSTOM EVENT: {event['data']} !!!")
        else:
            print(f"Event: {kind} from {name}")

asyncio.run(main())
