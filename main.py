import asyncio
import websockets
import ssl
import certifi
import json
import random
import pydantic

from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from enum import Enum
from typing import List, Dict, Optional


bots: List[AsyncTeleBot] = [AsyncTeleBot(token, parse_mode='html', disable_web_page_preview=True) for token in \
    [
        # '1234567890:abcdefghijklmnopqrstuvwxyzABCDEFGHIJ',
    ]
]

MINLIMIT = 3000

url = "wss://cables.geckoterminal.com/cable"
headers = {"Origin": "https://www.geckoterminal.com"}

ssl_context: ssl.SSLContext = ssl.create_default_context(cafile=certifi.where())


class Channels(str, Enum):
    GRAM = -1002215677593
    NOT = -1002151931451
    TON = -1002202204337


class Pool(pydantic.BaseModel) :
    dex: str
    source_id: int     
    target_id: int     
    source_sbl: str    
    target_sbl: str    
    channel: Channels
    min_limit: Optional[int] = MINLIMIT


class TransactionTypes(str, Enum):
    buy = "buy"
    sell = "sell"


pools: Dict[int, Pool] = \
    {
        163507685 : Pool(dex="StonFI", source_id=30977166, target_id=31484035, source_sbl="TON", target_sbl="GRAM", channel=Channels.GRAM),
        163500022 : Pool(dex="Dedust", source_id=30977166, target_id=31484035, source_sbl="TON", target_sbl="GRAM", channel=Channels.GRAM),
        164340393 : Pool(dex="StonFI", source_id=30977166, target_id=32894698, source_sbl="TON", target_sbl="NOT", channel=Channels.NOT),
        164265614 : Pool(dex="Dedust", source_id=30977166, target_id=32894698, source_sbl="TON", target_sbl="NOT", channel=Channels.NOT),
        164341132 : Pool(dex="StonFI", source_id=32513444, target_id=32894698, source_sbl="USD₮", target_sbl="NOT", channel=Channels.NOT),
        164096462 : Pool(dex="StonFI", source_id=32513444, target_id=31484035, source_sbl="USD₮", target_sbl="GRAM", channel=Channels.GRAM),
        164094613 : Pool(dex="StonFI", source_id=32513444, target_id=30977166, source_sbl="USD₮", target_sbl="TON", channel=Channels.TON, min_limit=10000), 
    }


class SocketData(pydantic.BaseModel) :
    block_timestamp : int 
    from_token_amount : float
    from_token_id : int 
    from_token_total_in_usd : float 
    pool : Pool 
    price_from : float 
    price_from_in_currency_token : float 
    price_from_in_usd : float 
    price_to : float 
    price_to_in_currency_token : float
    price_to_in_usd : float 
    to_token_amount : float 
    to_token_id : int 
    to_token_total_in_usd : float 
    tx_from_address : str 
    tx_hash : str 

    @property
    def type(self): return TransactionTypes.buy if self.pool.source_id == self.from_token_id else TransactionTypes.sell

    @property
    def buying(self): return self.type == TransactionTypes.buy

    @property
    def poolstr(self): return self.pool.target_sbl + '/' + self.pool.source_sbl

    @property
    def price_in_usd(self): return self.price_to_in_usd if self.buying else self.price_from_in_usd

    @property
    def channel_id(self): return self.pool.channel.value

    @property
    def type_emoji(self): return "🟢" if self.buying else "🔴"

    @property
    def type_desc(self): return "Покупка" if self.buying else "Продажа"

    @property
    def amount(self): return self.to_token_amount if self.buying else self.from_token_amount

    @property
    def price_in_source(self): return (1 / self.price_from_in_currency_token) * self.price_to_in_currency_token if self.buying else (1 / self.price_to_in_currency_token) * self.price_from_in_currency_token




async def connect_pool(pool_id):
    async with websockets.connect(url, ssl=ssl_context, extra_headers=headers) as ws:
        try:
            data = {"command": "subscribe", "identifier": json.dumps({"channel": "SwapChannel", "pool_id": pool_id})}
            await ws.send(json.dumps(data))
            async for message in ws:
                await handle_message(json.loads(message))
        except Exception as e:
            print(f"Error during connection or message handling: {e}")


async def handle_message(message: dict):
    message: Optional[Dict] = message.get('message')
    
    if not message or type(message) is not dict or message['type'] != "newSwap": return

    data = message['data']


    data['pool'] = pools[data['pool_id']]
    data = SocketData(**message['data'])
    
    if data.from_token_total_in_usd < data.pool.min_limit: return
    text = \
\
f"""
<b>{data.type_emoji} {data.type_desc} {data.poolstr}</b>

Кол-во: <b>{round(data.amount, 4)} {data.pool.target_sbl} (${round(data.to_token_total_in_usd, 2)})</b>
Адрес: <a href='https://tonviewer.com/{data.tx_from_address}'>{data.tx_from_address[:4]}...{data.tx_from_address[-4:]}</a>
Биржа: <b>{data.pool.dex}</b>

Курс:
<b>{round(data.price_in_source, 6)} {data.pool.source_sbl} (${round(data.price_in_usd, 5)})</b>
"""
    
    keyboard = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(text='🔗  Транзакция', url=f'https://tonviewer.com/transaction/{data.tx_hash}'),
        InlineKeyboardButton(text='🔗  Адрес кошелька', url=f'https://tonviewer.com/{data.tx_from_address}')
    )

    bot = random.choice(bots)

    await bot.send_message(
        chat_id=data.channel_id,
        text=text,
        reply_markup=keyboard
    )
    

async def main():
    while True:
        try:
            tasks = []
            for pool_id in pools:
                tasks.append(asyncio.create_task(connect_pool(pool_id)))
            await asyncio.gather(*tasks)
        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())
