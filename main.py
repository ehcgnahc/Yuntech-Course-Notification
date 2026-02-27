import asyncio
from crawler import crawler
from notification import notification

async def main():
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()
    notification_task = asyncio.create_task(notification(queue))
    crawler_task = asyncio.create_task(asyncio.to_thread(crawler, loop, queue))
    await asyncio.gather(notification_task, crawler_task)

if __name__ == '__main__':
    asyncio.run(main())