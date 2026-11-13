import asyncio, sys
sys.path.insert(0,'d:/QuantPortfolio')
from backend.database import AsyncSessionLocal
from backend.models.user import users
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as s:
        r = await s.execute(select(users))
        rows = r.mappings().all()
        print(f'Users in DB: {len(rows)}')
        for row in rows:
            print(f'  email={row["email"]}')

asyncio.run(check())
