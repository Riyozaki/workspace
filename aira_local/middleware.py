"""Bound request bodies before JSON parsing; never buffer unbounded input."""
import asyncio
from starlette.responses import JSONResponse


class BodyLimitMiddleware:
 def __init__(self,app,max_bytes=131072):self.app=app;self.max_bytes=max_bytes
 async def __call__(self,scope,receive,send):
  if scope['type']!='http' or scope.get('method') not in ('POST','PUT','PATCH'):
   return await self.app(scope,receive,send)
  headers=dict(scope.get('headers',[]))
  try:
   if int(headers.get(b'content-length',b'0'))>self.max_bytes:
    return await JSONResponse({'detail':'Request exceeds the prototype input budget'},413)(scope,receive,send)
  except ValueError:
   return await JSONResponse({'detail':'Invalid content length'},400)(scope,receive,send)
  parts=[];size=0
  while True:
   try:message=await asyncio.wait_for(receive(),timeout=10.)
   except asyncio.TimeoutError:return await JSONResponse({'detail':'Request body timeout'},408)(scope,receive,send)
   if message['type']=='http.disconnect':return
   chunk=message.get('body',b'');size+=len(chunk)
   if size>self.max_bytes:return await JSONResponse({'detail':'Request exceeds the prototype input budget'},413)(scope,receive,send)
   parts.append(chunk)
   if not message.get('more_body',False):break
  body=b''.join(parts);del parts;delivered=False
  async def bounded_receive():
   nonlocal delivered
   if not delivered:delivered=True;return {'type':'http.request','body':body,'more_body':False}
   return await receive()
  await self.app(scope,bounded_receive,send)
