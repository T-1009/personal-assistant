import asyncio
from contextvars import ContextVar

test_var = ContextVar('test_var', default=None)

async def tool_callback():
    val = test_var.get()
    print(f"Tool callback got: {val}")

async def async_wrapper():
    await tool_callback()

async def astream_events():
    yield "start"
    # LangGraph executes tool in a new task
    task = asyncio.create_task(async_wrapper())
    await task
    yield "end"

async def pump(q):
    test_var.set(q)
    async for event in astream_events():
        pass

async def main():
    q = asyncio.Queue()
    await pump(q)

asyncio.run(main())
