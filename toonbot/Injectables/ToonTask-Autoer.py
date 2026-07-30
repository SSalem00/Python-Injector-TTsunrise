import urllib
import random
import time
from direct.interval.IntervalGlobal import *
from direct.gui.DirectLabel import DirectLabel
from toontown.toon import DistributedNPCToon
from toontown.toonbase import ToontownGlobals
from toontown.safezone import Playground
from toontown.classicchars import *
from toontown.battle import SuitBattleGlobals
from toontown.building import DistributedBuilding
from toontown.battle import DistributedBattleBldg
from toontown.suit import SuitDNA
from toontown.quest import Quests
from toontown.quest import QuestBookPoster
from toontown.toon import ToonHead
from toontown.building import DistributedDoor
from toontown.safezone import DistributedPartyGate
from toontown.safezone import DistributedTrolley
from toontown.toon import DistributedNPCFisherman
from toontown.toon import DistributedNPCPartyPerson
from toontown.shtiker import PurchaseManager
from toontown.minigame import DistributedMinigame
from toontown.estate import Estate
from toontown.estate import House
from toontown.hood import ZoneUtil

HQZONES=[10000, 11000, 12000, 13000]

execfile('TaskBot/Toontask Bot.py',globals())    
taskAutoer=TaskAutoer()

execfile('TaskBot/Building Autoer Toontask.py',globals())
buildingAutoer=BuildingAutoer()

execfile('TaskBot/Gag Trainer Toontask.py',globals())
gagTrainer=GagTrainer()

execfile('TaskBot/Vp Maxer Toontask.py',globals())
vpMaxer=VPMaxer()

execfile('TaskBot/Cfo Maxer Toontask.py',globals())
cfoMaxer=CFOmaxer()

execfile('TaskBot/Ceo Maxer Toontask.py',globals())
ceoMaxer=CEOMaxer()

taskAutoer.checkWhatToDo()
