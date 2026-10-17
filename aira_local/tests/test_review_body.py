import asyncio
import pytest
from aira_local.middleware import BodyLimitMiddleware


def test_total_body_timeout_cannot_be_reset_by_slow_chunks():
 async def run():
  called=False;messages=[]
  async def app(scope,receive,send):
   nonlocal called;called=True
  async def receive():
   await asyncio.sleep(.025)
   return {'type':'http.request','body':b'x','more_body':True}
  async def send(event):messages.append(event)
  middleware=BodyLimitMiddleware(app,read_timeout=.06)
  await middleware({'type':'http','method':'POST','headers':[]},receive,send)
  assert not called;assert messages[0]['status']==408
 asyncio.run(run())
