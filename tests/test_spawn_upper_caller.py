"""Strict direct-table qualification for 1B735E upper creation."""
from ctypes import memmove
from pathlib import Path
import pytest
from aladdin_sega import artifacts
from aladdin_sega.boundary import SPAWN_UPPER_CALLER_ENTRY
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, read_rom
from aladdin_sega.recovery import Candidate
FIXTURES=tuple(Path('artifacts/grinding/luna/dispatcher-1ae3fc').glob('*/*/1B735E.alsnap'))
assert FIXTURES
def run(path,candidate=False,cap=None,exhaust=False):
 with Machine(read_rom(DEFAULT_ROM)) as m:
  artifacts.restore_snapshot(m,path.read_bytes())
  if cap is not None: memmove(m.ram_address+0xefe0,cap.to_bytes(2,'big'),2)
  if exhaust:
   for i in range(20): memmove(m.ram_address+((0xff7f06+i*0x42)&0xffff),b'\1',1)
  r=m.registers(); outer=int.from_bytes(m.peek_ram(r['a7']&65535,4),'big')&0xffffff
  stats=None
  if candidate:
   c=Candidate('lifecycle');c.arm(m);assert m.run(instructions=1)=='gate';assert c.on_gate(m,m.info['tick']+1000000);stats=c.stats
  m.gates([outer]);assert m.run(instructions=5000)=='gate'; state=(artifacts.snapshot_bytes(m),m.info,m.registers(),m.frame()[2],m.audio())
  m.gates([]);assert m.run(instructions=150)=='limit';return state,(artifacts.snapshot_bytes(m),m.info,m.frame()[2],m.audio()),stats
@pytest.mark.parametrize('path',FIXTURES)
@pytest.mark.parametrize('cap,exhaust',[(None,False),(0x3939,False),(None,True)])
def test_upper_caller_outer_and_future(path,cap,exhaust):
 a,af,_=run(path,False,cap,exhaust);b,bf,s=run(path,True,cap,exhaust);assert a==b and af==bf and s['spawn_caller_hits']==1
def test_upper_caller_deadline_keeps_original():
 p=FIXTURES[0];a,af,_=run(p);
 with Machine(read_rom(DEFAULT_ROM)) as m:
  artifacts.restore_snapshot(m,p.read_bytes());r=m.registers();outer=int.from_bytes(m.peek_ram(r['a7']&65535,4),'big')&0xffffff;c=Candidate('lifecycle');c.arm(m);assert m.run(instructions=1)=='gate';assert not c.on_gate(m,m.info['tick']+1);m.gates([outer]);assert m.run(instructions=5000)=='gate';assert (artifacts.snapshot_bytes(m),m.info,m.registers(),m.frame()[2],m.audio())==a
