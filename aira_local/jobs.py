"""Bounded per-request stream state; a consumer cannot own the model lock."""
from __future__ import annotations
import queue,threading,time,uuid


class ChatJob:
 def __init__(self,max_seconds=60.,queue_size=64):
  self.id=uuid.uuid4().hex;self.cancel=threading.Event();self.finished=threading.Event()
  self.events=queue.Queue(maxsize=queue_size);self.started=time.perf_counter();self.deadline=self.started+max_seconds;self.thread=None;self.metrics=None;self.cancel_reason=None
 def request_cancel(self,reason):
  if self.cancel_reason is None:self.cancel_reason=reason
  self.cancel.set()
 def emit(self,event):
  if self.cancel.is_set():return False
  if time.perf_counter()>=self.deadline:self.request_cancel('timeout');return False
  try:self.events.put(event,timeout=.5);return True
  except queue.Full:self.request_cancel('slow_client');return False
 def complete(self,metrics):
  self.metrics=metrics
  # Terminal delivery may not wait on a disconnected/slow client. The producer
  # has already cleaned up and released the model gate before calling this.
  try:self.events.put_nowait({'type':'done','metrics':metrics})
  except queue.Full:
   try:self.events.get_nowait()
   except queue.Empty:pass
   try:self.events.put_nowait({'type':'done','metrics':metrics})
   except queue.Full:pass
  self.finished.set()
