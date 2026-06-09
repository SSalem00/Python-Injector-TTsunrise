class TaskAutoer:
    oldTeleportInPlayground=Playground.Playground.exitTeleportIn
    #oldBattleBldg=DistributedBattleBldg.DistributedBattleBldg.__init__
    #oldBuildingGenerate=DistributedBuilding.DistributedBuilding.generate
    #oldEnterToon=DistributedBuilding.DistributedBuilding.enterToon
    oldMiniGameAnnounceGenerate=DistributedMinigame.DistributedMinigame.announceGenerate
    oldPurchangeManagerAnnouncGenerate=PurchaseManager.PurchaseManager.announceGenerate
    oldEstateTeleportIn=Estate.Estate.exitTeleportIn
    oldHouseDoorIn=House.House.exitDoorIn

    def newWalk(self, a, b, c, d=0, e=0):
        pass

    def __init__(self):
        DistributedMinigame.DistributedMinigame.announceGenerate=lambda newSelf: self.newMiniGameAnnounceGenerate(newSelf)
        PurchaseManager.PurchaseManager.announceGenerate=lambda newSelf: self.newPurchangeManagerAnnouncGenerate(newSelf)
        Playground.Playground.exitTeleportIn=lambda newSelf,*args,**kwds: self.newTeleportInPlayground(newSelf,*args,**kwds)
        Estate.Estate.exitTeleportIn=lambda newSelf,*args,**kwds: self.newEstateTeleportIn(newSelf,*args,**kwds)
        House.House.exitDoorIn=lambda newSelf,*args,**kwds: self.newHouseDoorIn(newSelf,*args,**kwds)
        #DistributedBuilding.DistributedBuilding.generate=lambda newSelf,*args: self.newBuildingGenerate(newSelf,*args)
        #DistributedBuilding.DistributedBuilding.enterToon=lambda newSelf,*args: self.newEnterToon(newSelf,*args)
        base.localAvatar.setWantBattles(False)
        self.shardIds=[]
        self.isMember=True
        self.jellybeansNeeded=500

        posterNumToPos = [(-0.6, 1, 0.5),
                          (-0.6, 1, 0.2),
                          (-0.2, 1, 0.5),
                          (-0.2, 1, 0.2)
                          ]

        self.questsGui = []
        for i in range(4):
            self.questsGui.append(QuestBookPoster.QuestBookPoster(pos = posterNumToPos[i], scale = 0.5))
            self.questsGui[-1].reparentTo(base.a2dRightCenter)
            self.questsGui[-1].mouseEnterPoster(0)
            self.questsGui[-1].mouseExitPoster=self.questsGui[-1].mouseEnterPoster

        self.oldNPCmovie=None

        self.updateQuestGuiLoop=Sequence()
        for i in range(4):
            self.updateQuestGuiLoop.append(Func(self.updateQuestGui, i))
            self.updateQuestGuiLoop.append(Wait(0.125))
        self.updateQuestGuiLoop.loop()

        Sequence(Func(self.collisionsOff),Wait(0.5)).loop()

        for shard in base.cr.activeDistrictMap:
            if base.cr.activeDistrictMap[shard].avatarCount<50:
                self.shardIds.append(shard)
        self.wantedTracks=[1,3] #Anyone looking into choosing your tracks this is all you need to change lol
        self.status=None
        self.buildingLevelToZoneDict={1:1000,2:5000,3:4000,4:3000,5:9000}
        DirectLabel(parent=aspect2d,relief=None,text='\x01shadow\x01Freshollies Toontask Autoer\x02',text_scale=0.17, pos=(0, 0, 0.87), text_fg=(1, 1, 1, 1))
        DirectLabel(parent=aspect2d,relief=None,text='\x01shadow\x01Freshollies Toontask Autoer\x02',text_scale=0.17, pos=(0, 0, 0.87), text_fg=(0, 0, 0, 0))
        self.questsAtNoneLeft = 5
        self.curTier = base.localAvatar.rewardTier
        #Certain tiers only have one quest (mainly the start and end of each playground). We shouldn't bother trying to fill our quests on these.
        self.tiersWithOneQuest = [Quests.TT_TIER,
                                  Quests.TT_TIER+3,
                                  Quests.DD_TIER,
                                  Quests.DD_TIER+2,
                                  Quests.MM_TIER,
                                  Quests.MM_TIER+2,
                                  Quests.BR_TIER,
                                  Quests.BR_TIER+2]
        for i in range(14):
            self.tiersWithOneQuest.append(Quests.LAWBOT_HQ_TIER+i)
        for i in range(17):
            self.tiersWithOneQuest.append(Quests.BOSSBOT_HQ_TIER+i)

        self.optimalSuitLocations = {'b': 5000,
        'bs': 3000,
        'ac': 3000,
        'sd': 3000,
        'cc': 11200,
        'tm': 11200,
        'nd': 11200,
        'gh': 11200,
        'ms': 11200,
        'ym': 1000,
        'mm': 3000,
        'nc': 12000}

        self.hqOfficersTalkedTo = []
        self.hqIdx = 0

        DistributedMickey.DistributedMickey.setWalk = self.newWalk
        DistributedDonald.DistributedDonald.setWalk = self.newWalk
        DistributedMinnie.DistributedMinnie.setWalk = self.newWalk
        DistributedDaisy.DistributedDaisy.setWalk = self.newWalk
        DistributedGoofy.DistributedGoofy.setWalk = self.newWalk
        DistributedGoofySpeedway.DistributedGoofySpeedway.setWalk = self.newWalk
        DistributedPluto.DistributedPluto.setWalk = self.newWalk
        DistributedChip.DistributedChip.setWalk = self.newWalk
        DistributedDale.DistributedDale.setWalk = self.newWalk
        DistributedDale.DistributedDale.setFollowChip = self.newWalk
        
                              
        
    def collisionsOff(self):
        try:
            base.localAvatar.collisionsOff()
        except:
            pass

    def newMiniGameAnnounceGenerate(self, newSelf):
        self.oldMiniGameAnnounceGenerate(newSelf)
        messenger.send('minigameAbort')

    def newPurchangeManagerAnnouncGenerate(self, newSelf):
        self.oldPurchangeManagerAnnouncGenerate(newSelf)
        Sequence(Wait(10),Func(self.skipTrolley)).start()

    def skipTrolley(self):
        for i in range(5):
            messenger.send('doneChatPage')
        Sequence(Wait(4),Func(messenger.send,'purchaseBackToToontown')).start()

    def newNPCmovie(self, mode, npcId, avId, quests, timestamp):
        self.oldNPCmovie(mode, npcId, avId, quests, timestamp)
        print("Npc movie started")
        realMovie = False
        validSalesLocs = [Quests.Anywhere, ToontownGlobals.SellbotHQ] #Sellbots are only valid picks if they're anywhere or specifically in SBHQ.
        curSuitDepts = []
        curBldgDepts = []
        mintQuests = [Quests.MintQuest, Quests.SupervisorQuest]
        for quest in base.localAvatar.quests:
            activeQuestObj = Quests.getQuest(quest[0])
            if activeQuestObj is None:
                continue

            if activeQuestObj.getType() == Quests.CogTrackQuest:
                curSuitDepts.append(activeQuestObj.getCogTrack())
                
            elif activeQuestObj.getType() == Quests.BuildingQuest and activeQuestObj.getBuildingTrack() != Quests.Any:
                curBldgDepts.append(activeQuestObj.getBuildingTrack())

            #This is so we only pick Cashbots if we have an active Mint related quest.
            elif activeQuestObj.getType() in mintQuests:
                curSuitDepts.append('m')
                
        if avId == base.localAvatar.doId:
            if not quests:
                base.localAvatar.setSystemMessage(0, "No quests!")
                #self.questsAtNoneLeft = len(base.localAvatar.quests)
                self.officer.setMovie = self.oldNPCmovie
                base.cr.playGame.getPlace().fsm.forceTransition('walk')
                return
            
            realMovie = True
            numJffTasks = 0
            offeredQuestLen = len(quests)/3
            for i in range(offeredQuestLen):
                #Quests list is a flattened list of [questId, rewardId, toNpcId], therefore base idx is (i*3).
                questId = quests[i*3]
                rewardId = quests[(i*3) + 1]
                toNpcId = quests[(i*3) + 2]
                
                print('iterating quest')
                questObj = Quests.getQuest(questId)
                questEntry = Quests.QuestDict.get(questId)
                validQuest = True

                if questEntry is not None:
                    if Quests.isRewardOptional(questEntry[Quests.QuestDictTierIndex], rewardId):
                        numJffTasks += 1
                        continue
            
                #Task choosing logic.
                
                if questId in [5217, 3244, 3210]:
                    #Generic bad task list.
                    validQuest = False

                if questObj is None:
                    validQuest = False
                
                elif questObj.getType() == Quests.CogQuest and questObj.getCogType() != Quests.Any:
                    validQuest = False
                
                elif questObj.getType() == Quests.CogTrackQuest:
                    if (curSuitDepts != [] and questObj.getCogTrack() not in curSuitDepts) or (curBldgDepts != [] and questObj.getCogTrack() not in curBldgDepts):
                        validQuest = False
                    
                    elif questObj.getCogTrack() == 's' and questObj.getLocation() not in validSalesLocs:
                        validQuest = False

                elif questObj.getType() == Quests.BuildingQuest and questId != 3222:
                    validQuest = False

                elif questObj.getType() in [Quests.SkelecogQuest, Quests.SkelecogLevelQuest]:
                    validQuest = False

                elif questObj.getType() == Quests.CogLevelQuest and questObj.getCogLevel() > 9:
                    validQuest = False

                elif questObj.getType() in mintQuests:
                    for curQuest in base.localAvatar.quests:
                        curQuestObj = Quests.getQuest(curQuest[0])
                        if curQuestObj.getType() in mintQuests and curQuestObj.getLocation() != questObj.getLocation():
                            validQuest = False
                            break
                            
                        elif curQuestObj.getType() == Quests.CogTrackQuest and (curQuestObj.getCogTrack() != 'm' or curQuestObj.getLocation() not in [Quests.Anywhere, 12000]):
                            validQuest = False
                            break

                
                if validQuest:
                    print('attemping to pick quest')
                    print(Quests.findFinalRewardId(questId)[0])
                    print(questId)
                    self.officer.sendChooseQuest(questId)
                    self.officer.sendUpdate('setMovieDone')
                    self.officer.setMovie=self.oldNPCmovie
                    base.cr.playGame.getPlace().fsm.forceTransition('walk')
                    
                    self.hqOfficersTalkedTo = []
                    self.hqIdx = 0
                    return
                                    
            if numJffTasks >= offeredQuestLen:
                self.questsAtNoneLeft = len(base.localAvatar.quests)

        self.officer.sendChooseQuest(0)
        self.officer.setMovie = self.oldNPCmovie
        base.cr.playGame.getPlace().fsm.forceTransition('walk')

    def newBuildingGenerate(self,newSelf,*args):
        try:
            oldBuildingGenerate(newSelf,*args)
        except:
            pass

    def newEnterToon(self,newSelf,*args):
        try:
            oldEnterToon(newSelf,*args)
        except:
            pass

    def newTeleportInPlayground(self,newSelf,*args,**kwds):
        self.oldTeleportInPlayground(newSelf,*args,**kwds)
        print("Teleported into the playground")
        if buildingAutoer.shouldContinue:

            buildingAutoer.checkStop()

            if buildingAutoer.shouldContinue and not self.isQuestComplete():
                buildingAutoer.killElevators.append(buildingAutoer.lastElevator)
                Sequence(Wait(2),Func(buildingAutoer.teleportBackToStreet)).start()

            else:
                Sequence(Wait(2),Func(self.checkWhatToDo)).start()

        elif gagTrainer.shouldContinue:
            Sequence(Wait(2),Func(gagTrainer.teleportBackToStreet)).start()

        else:
            Sequence(Wait(2),Func(self.checkWhatToDo)).start()

    def newEstateTeleportIn(self,newSelf,*args,**kwds):
        self.oldEstateTeleportIn(newSelf,*args,**kwds)
        for door in base.cr.doFindAll('Door'):
            if 'esHouse_1' in str(door.getBuilding()):
                door.sendUpdate('requestEnter')

    def newHouseDoorIn(self,newSelf,*args,**kwds):
        self.oldHouseDoorIn(newSelf,*args,**kwds)
        base.cr.doFind('phone').sendUpdate('avatarEnter')
        base.cr.doFind('phone').sendUpdate('avatarExit')
        Sequence(Wait(2),Func(self.checkWhatToDo)).start()

    def checkWhatToDo(self):
        print("Checking what to do:")
        print("We have %s Tasks" %(len(base.localAvatar.quests)))
        print("We are going to try and collect %s Tasks from HQ" %(self.questsAtNoneLeft))

        if self.curTier != base.localAvatar.rewardTier:
            # Our tier updated! That means we should reset the quests at none left.
            self.questsAtNoneLeft = 5
            self.curTier = base.localAvatar.rewardTier

        if base.localAvatar.getTotalMoney()>self.jellybeansNeeded:
            print("We have all the money we need")
            self.jellybeansNeeded=500
        
        if base.localAvatar.defaultShard not in self.shardIds:
            print("We need to teleport to an empty district")
            base.cr.playGame.getPlace().requestTeleport(2000,2000, random.choice(self.shardIds),None)
        

        elif self.status=='Fishing':
            print("We are completing a fishing task")
            if not self.isQuestComplete():
                self.fishOnce()
            else:
                print("Fishing task is done")
                for dock in base.cr.doFindAll('DistributedFishingSpot'):
                    dock.sendUpdate('requestExit')

                self.status=None
                self.doTask()

        elif self.jellybeansNeeded == 12000:
            print("We are continuing to fish for money")
            self.fishOnce()

        elif base.localAvatar.getTotalMoney()<self.jellybeansNeeded:
            print("We need to fish for money")
            self.jellybeansNeeded = 12000
            if base.localAvatar.getTotalMoney() < 1:
                base.localAvatar.setSystemMessage(0, "This script needs at least 1 JB to run")
                self.jellybeansNeeded = 500
                self.doTrolleyTask()
            elif base.localAvatar.getZoneId() == 2000:
                self.fishOnce()
            else:
                base.cr.playGame.getPlace().requestTeleport(2000, 2000, None, None)

        elif len(base.localAvatar.quests) >= base.localAvatar.getQuestCarryLimit() or \
                        len(base.localAvatar.quests) >= self.questsAtNoneLeft or \
                        (self.curTier in self.tiersWithOneQuest and len(base.localAvatar.quests) == 1):
            print('Doing task')
            self.doTask()
        else:
            print("We have nothing to do so collect a task")
            if len(base.localAvatar.quests) < self.questsAtNoneLeft:
                self.collectNewTask()

    def updateQuestGui(self, i):
        if len(base.localAvatar.quests) >= i+1:
            self.questsGui[i].update(base.localAvatar.quests[i])
        else:
            self.questsGui[i].clear()

    def getCurrentQuest(self):
        return Quests.getQuest(base.localAvatar.quests[0][0])

    def getBestZoneForCogLevel(self,level):
        if self.isMember:
            if level<3:
                return 2000
            elif level<4:
                return 1000
            elif level<5:
                return 5000
            elif level<6:
                return 4000
            elif level<7:
                return 3000
            elif level<8:
                return 9000
            elif level<9:
                return 12000
            else:
                return 13000
        else:
            return 2000

    def getBestZoneForBuildingLevel(self,level):
        return self.buildingLevelToZoneDict.get(level)

    def getSuitName(self,suitType):
        try:
            return SuitBattleGlobals.SuitAttributes[suitType].get('name')
        except:
            return suitType

    def getCogLevelFromCog(self,suitType):
        try:
            return SuitBattleGlobals.SuitAttributes[suitType].get('level')+1
        except:
            return 1


    def getSuitDepartment(self,suitType):
        return SuitDNA.getSuitDept(suitType)

    def getCorrectChoice(self,choices):
        currentTracks = base.localAvatar.getTrackAccess()
        if 0 in choices and not currentTracks[0]:
            return 0
        elif 2 in choices and not currentTracks[2]:
            return 2
        elif self.wantedTracks[0] in choices:
            return self.wantedTracks[0]
        else:
            return self.wantedTracks[1]

    def newTask(self):
        print('collecting new task')
        officer = None
        for potentialOfficer in base.cr.doFindAll('HQ Officer'):
            officerId = potentialOfficer.doId #This can change per district, but we only talk with interest in one district... Should be okay?
            if potentialOfficer.allowedToTalk() and officerId not in self.hqOfficersTalkedTo:
                officer = potentialOfficer
                self.hqOfficersTalkedTo.append(officerId)
                break
        
        if officer is not None:
            if officer.setMovie != self.oldNPCmovie:
                self.oldNPCmovie = officer.setMovie
                print('setting old movie function')
            self.officer=officer
            officer.setMovie=self.newNPCmovie
            officer.sendUpdate('avatarEnter')

    def collectNewTask(self):
        hqs = [2742, 2832, 1507, 1629, 1729, 1835, 3508, 3654, 3739, 3801, 4504, 4659, 4739, 4873, 5502, 5627, 5728, 5802, 9505, 9652, 9756]
        if self.hqIdx > len(hqs) - 1:
            self.hqIdx = 0
        hq = hqs[self.hqIdx]
        self.hqIdx += 1
        interest=base.cr.addInterest(base.localAvatar.defaultShard, hq, description='5', event=None)
        Sequence(Wait(1),Func(self.newTask),Wait(2),Func(base.cr.removeInterest,interest),Func(self.checkWhatToDo)).start()

    def nextShard(self):
        if self.shardIds[0] == base.localAvatar.defaultShard:
            self.shardIds.append(self.shardIds[0])
            del self.shardIds[0]

        base.cr.playGame.getPlace().fsm.forceTransition('walk')
        base.cr.playGame.getPlace().requestTeleport(2000,2000,self.shardIds[0],None)
        self.shardIds.append(self.shardIds[0])
        del self.shardIds[0]

    def getFishSpot(self):
        for spot in base.cr.doFindAllInstances(DistributedFishingSpot.DistributedFishingSpot):
            if spot.avId==base.localAvatar.doId:
                return spot

        base.localAvatar.setSystemMessage(0,'Not at a spot')
        return False

    def catchFish(self):
        try:
            fish = base.cr.doFindAll("FishingTarget")[0]
            for fp in base.cr.doFindAll("FishingPond"):
                spot=self.getFishSpot()
                if spot:
                    spot.sendUpdate('doCast',[1,1])
                    fp.sendUpdate('hitTarget',[fish.doId])
        except:
            pass

    def fishOnce(self):
        entered=False
        for spot in reversed(base.cr.doFindAll('DistributedFishingSpot')):
            if spot.allowedToEnter():
                entered=True
                spot.sendUpdate('requestEnter')
                usedSpot=spot
                break
        if entered:
            catchFishSeq=Sequence()
            catchFishSeq.append(Wait(1))
            for i in range(23):
                catchFishSeq.append(Func(self.catchFish))
                catchFishSeq.append(Wait(0.05))
            catchFishSeq.append(Wait(1))
            catchFishSeq.append(Func(self.sellFish))
            catchFishSeq.append(Wait(0.5))
            catchFishSeq.append(Func(self.checkWhatToDo))
            catchFishSeq.start()
        else:
            Sequence(Wait(2),Func(self.fishOnce)).start()

    def sellFish(self):
        base.cr.doFind('Fisherman').sendUpdate('avatarEnter')
        base.cr.doFind('Fisherman').sendUpdate('completeSale',[1])

    def speakToNpc(self,name):
        if base.cr.doFind(name):
            for npc in base.cr.doFindAllInstances(DistributedNPCToon.DistributedNPCToon):
                if npc.getName()==name:
                    if npc.allowedToTalk():
                        npc.sendUpdate('avatarEnter')
                        npc.sendUpdate('setMovieDone')
                        base.cr.removeInterest(self.interest)
                        Sequence(Wait(1),Func(self.checkWhatToDo)).start()
                        found=True
                        foundNPC=True
                        break
                    else:
                        found=False
                        foundNPC=True
                else:
                    foundNPC=False
            if not foundNPC:
                Sequence(Func(base.cr.removeInterest,self.interest),Wait(0.5),Func(self.nextShard)).start()
            elif not found:
                Sequence(Wait(5),Func(self.speakToNpc,name)).start()
        else:
            Sequence(Func(base.cr.removeInterest,self.interest),Wait(0.5),Func(self.nextShard)).start()

    def chooseTrack(self,name):
        if base.cr.doFind(name):
            for npc in base.cr.doFindAllInstances(DistributedNPCToon.DistributedNPCToon):
                if npc.getName()==name:
                    if npc.allowedToTalk():
                        npc.sendUpdate('avatarEnter')
                        try:
                            npc.sendChooseTrack(self.getCorrectChoice(self.getCurrentQuest().getChoices()))
                            npc.sendUpdate('setMovieDone')
                        except:
                            pass
                        base.cr.removeInterest(self.interest)
                        Sequence(Wait(0.5),Func(self.checkWhatToDo)).start()
                        found=True
                        foundNPC=True
                        break
                    else:
                        found=False
                        foundNPC=True
                else:
                    foundNPC=False
            if not foundNPC:
                Sequence(Func(base.cr.removeInterest,self.interest),Wait(0.5),Func(self.nextShard)).start()
            elif not found:
                Sequence(Wait(5),Func(self.chooseTrack)).start()
        else:
            Sequence(Func(base.cr.removeInterest,self.interest),Wait(0.5),Func(self.nextShard)).start()

    def doFriendTask(self):
        print("Sending invite to self")
        def acceptInvite(inviterId, inviterName, inviterDna, context):
            print("Adding self")
            if (inviterId == base.localAvatar.doId):
                base.cr.friendManager.sendUpdate("inviteeFriendResponse", [1, context])
                base.ignore("friendInvitation")
                print("Completed friend task")
                messenger.send("cancelFriendInvitation")
                Sequence(Wait(2), Func(self.checkWhatToDo)).start()

        base.accept("friendInvitation", acceptInvite)
        base.cr.friendManager.sendUpdate('friendQuery', [base.localAvatar.doId])

    def doTrolleyTask(self):
        if base.localAvatar.getZoneId() == 2000:
            if base.cr.doFind('Trolley').allowedToEnter():
                base.localAvatar.setPos(-133.548, -71.1069, 0.525)
                base.cr.playGame.getPlace().fsm.forceTransition('walk')
            else:
                Sequence(Wait(2),Func(self.doTrolleyTask)).start()
        else:
            base.cr.playGame.getPlace().requestTeleport(2000, 2000, None, None)


    def doNPCTask(self, isTrackTask, idx):
        try:
            if not self.isQuestComplete():
                questNum = idx
            else:
                questNum = self.isQuestComplete()[0]
            questList=base.localAvatar.quests
            zoneId=Quests.NPCToons.getNPCZone(questList[questNum][2])
            listedDict=list(Quests.NPCToons.NPCToonDict)
            try:
                npcName=Quests.getNpcInfo(questList[questNum][2])[0]
            except:
                npcName='HQ Officer'
                self.questsAtNoneLeft = 5
            if listedDict.count(questList[questNum][2])==1:
                if zoneId == -1:
                    zoneId = 2742
                self.interest=base.cr.addInterest(base.localAvatar.defaultShard, zoneId, description='5', event=None)
                if not isTrackTask:
                    Sequence(Wait(2),Func(self.speakToNpc,npcName)).start()
                else:
                    Sequence(Wait(2),Func(self.chooseTrack,npcName)).start()
        except:
            print('Error in completing task')
            Sequence(Wait(2), Func(self.checkWhatToDo)).start()

    def doTask(self):        

        if not base.localAvatar.quests:
            self.collectNewTask()
            return

        quest = None
        highPrio = [Quests.VisitQuest, Quests.DeliverItemQuest, Quests.DeliverGagQuest, Quests.FriendQuest, Quests.PhoneQuest, Quests.TrackChoiceQuest]
        #Priority list - higher indexes are lower priority.
        priorityList = [Quests.MintQuest, Quests.SupervisorQuest, Quests.FactoryQuest, Quests.ForemanQuest, Quests.BuildingQuest, Quests.CogTrackQuest, Quests.CogLevelQuest, Quests.CogQuest]
        idx = 0
        itr = -1
        protectedQuest = False
        locationNeeded = None
                
        #Priority logic.
        for q in base.localAvatar.quests:
            oldQuest = quest
            thisQuest = Quests.getQuest(q[0])
            questType = thisQuest.getType()
            itr += 1

            #Remove rogue JFF tasks.
            if Quests.isQuestJustForFun(q[0], q[3]):
                base.localAvatar.d_requestDeleteQuest(q)
                continue
            
            #Visit quests come first.
            if questType in highPrio:
                idx = itr
                quest = thisQuest
                break

            #Location quests should almost always be prioritised, and then further prioritised based on our normal logic.
            locCheck = locationNeeded is None or thisQuest.getLocation() == locationNeeded or (locationNeeded == 12000 and thisQuest.getLocation() in [12500, 12600, 12700])
            
            if questType == Quests.RecoverItemQuest:
                idx = itr
                quest = thisQuest
                protectedQuest = True
                continue

            if protectedQuest:
                continue
            
            if questType == Quests.CogQuest and thisQuest.getCogType() != Quests.Any:
                idx = itr
                quest = thisQuest
                protectedQuest = True
                continue

            if oldQuest is None:
                idx = itr
                quest = thisQuest
                if thisQuest.getLocation() != Quests.Anywhere:
                    locationNeeded = thisQuest.getLocation()
                continue

            oldQuestType = oldQuest.getType()

            if thisQuest.getLocation() != Quests.Anywhere and locationNeeded is None:
                idx = itr
                quest = thisQuest
                locationNeeded = thisQuest.getLocation()
                continue
 
            if priorityList.index(questType) < priorityList.index(oldQuestType) and locCheck:
                idx = itr
                quest = thisQuest
                continue
            
            elif priorityList.index(questType) == priorityList.index(oldQuestType) and locCheck:
                if questType == Quests.BuildingQuest:
                    if thisQuest.getNumFloors() >= oldQuest.getNumFloors() or (thisQuest.getBuildingTrack() != Quests.Any and oldQuest.getBuildingTrack() == Quests.Any):
                        idx = itr
                        quest = thisQuest
                        continue
                    
                if questType == Quests.CogLevelQuest and thisQuest.getCogLevel() > oldQuest.getCogLevel():
                    idx = itr
                    quest = thisQuest
                    continue


        #quest = Quests.getQuest(base.localAvatar.quests[0][0])

        if self.isQuestComplete() or quest.getType() == Quests.VisitQuest:
            self.doNPCTask(False, idx)

        elif quest.getType()==Quests.DeliverItemQuest:
            self.doNPCTask(False, idx)

        elif quest.getType() in (Quests.CogQuest,Quests.CogLevelQuest,Quests.CogTrackQuest):
            buildingAutoer.clearSettings()
            gagTrainer.clearSettings()

            if quest.getLocation()==11500:
                vpMaxer.otherFunctions.onlyDoFactory()
                vpMaxer.otherFunctions.start()

            elif quest.getType()==Quests.CogTrackQuest:
                if quest.getLocation()==1:
                    if base.localAvatar.getMaxHp()<30:
                        location=2000
                    elif quest.getCogType() == 'c':
                        location = 3000
                    elif quest.getCogType()=='s':
                        location=11200
                    elif quest.getCogType()=='m':
                        if base.localAvatar.getMaxHp() > 40:
                            location=12000
                        else:
                            location = 4000 #MML
                    else:
                        if base.localAvatar.getMaxHp() > 60: 
                            location=13000
                        else:
                            location = 5000 #DG
                    gagTrainer.setLocation(location)
                else:
                    gagTrainer.setLocation(quest.getLocation())
                gagTrainer.setCogType(quest.getCogType())
                gagTrainer.start()

            elif quest.getType()==Quests.CogLevelQuest:
                if not base.localAvatar.getTrackAccess()[2] or quest.getLocation() in HQZONES or quest.getCogLevel()<11 or quest.getLocation() in (12500,12600,12700):
                    if quest.getLocation()==1:
                        gagTrainer.setLocation(self.getBestZoneForCogLevel(quest.getCogLevel()+1))
                        nonGag=False
                    else:
                        if quest.getLocation() in (12500,12600,12700):
                            cfoMaxer.otherFunctions.onlyLast=False
                            cfoMaxer.otherFunctions.onlyDoMint()
                            cfoMaxer.mintAutoer.setType(quest.getLocation())
                            cfoMaxer.otherFunctions.start()
                            nonGag=True
                        elif quest.getLocation()==11500:
                            vpMaxer.otherFunctions.onlyLast=False
                            vpMaxer.otherFunctions.onlyDoFactory()
                            vpMaxer.otherFunctions.start()
                            nonGag=True
                        else:
                            gagTrainer.setLocation(quest.getLocation())
                            nonGag=False

                    if quest.getCogType()==1:
                        gagTrainer.setCogLevel(quest.getCogLevel())
                    else:
                        gagTrainer.setCogName(self.getSuitName(quest.getCogType()))
                        #gagTrainer.setLocation(self.getBestZoneForCogType(quest.getCogType)
                    if not nonGag:
                        gagTrainer.start()
                else:
                    if quest.getCogType()==1:
                        buildingAutoer.setBuildingType('')
                        buildingAutoer.setNumFloors(4)
                    else:
                        buildingAutoer.setBuildingType(self.getSuitDepartment(self.getCogType()))
                        buildingAutoer.setNumFloors(4)

                    if quest.getLocation()!=1:
                        buildingAutoer.setLocation(quest.getLocation())
                    else:
                        if base.localAvatar.getMaxHp()>70:
                            buildingAutoer.setLocation(self.getBestZoneForBuildingLevel(5))
                        else:
                            buildingAutoer.setLocation(self.getBestZoneForBuildingLevel(4))
                    buildingAutoer.start()
            else:
                if not base.localAvatar.getTrackAccess()[2] or quest.getLocation() in HQZONES or self.getCogLevelFromCog(quest.getCogType())+4<11:

                    if quest.getLocation()==1:
                        if base.localAvatar.getMaxHp()>30 and quest.getCogType()==1:
                            gagTrainer.setLocation(11200)
                        else:
                            optimalLoc = self.optimalSuitLocations.get(quest.getCogType(), self.getBestZoneForCogLevel(self.getCogLevelFromCog(quest.getCogType())+1)) 
                            gagTrainer.setLocation(optimalLoc)
                    else:
                        gagTrainer.setLocation(quest.getLocation())

                    if quest.getCogType()==1:
                        gagTrainer.setCogName(None)
                    else:
                        gagTrainer.setCogName(self.getSuitName(quest.getCogType()))
                    gagTrainer.start()
                else:
                    if quest.getCogType()==1:
                        buildingAutoer.setBuildingType('')
                        buildingAutoer.setNumFloors(4)
                    else:
                        buildingAutoer.setBuildingType(self.getSuitDepartment(quest.getCogType()))
                        buildingAutoer.setNumFloors(4)

                    if quest.getLocation()!=1:
                        buildingAutoer.setLocation(quest.getLocation())
                    else:
                        if base.localAvatar.getMaxHp()>70:
                            buildingAutoer.setLocation(self.getBestZoneForBuildingLevel(5))
                        else:
                            buildingAutoer.setLocation(self.getBestZoneForBuildingLevel(4))
                        buildingAutoer.shouldChangeHood = True
                    buildingAutoer.start()

        elif quest.getType()==Quests.BuildingQuest:
            print('Doing building quest')
            buildingAutoer.clearSettings()
            if quest.getLocation()==1:
                buildingAutoer.setLocation(self.getBestZoneForBuildingLevel(quest.getNumFloors()))
                buildingAutoer.shouldChangeHood=True
            else:
                buildingAutoer.setLocation(quest.getLocation())

            buildingAutoer.setNumFloors(quest.getNumFloors())

            if quest.getBuildingTrack()==1:
                #Check to see if we have other department related quests that could be fulfilled at the same time.
                wantedDept = ''
                for q in base.localAvatar.quests:
                    otherQuest = Quests.getQuest(q[0])
                    if otherQuest.getLocation() in [Quests.Anywhere, quest.getLocation()]:
                        if otherQuest.getType() == Quests.CogTrackQuest:
                            wantedDept = otherQuest.getCogTrack()
                            break
                        
                        elif otherQuest.getType() == Quests.CogQuest and otherQuest.getCogType() != Quests.Any:
                            wantedDept = self.getSuitDepartment(otherQuest.getCogType())
                            continue
                
                buildingAutoer.setBuildingType(wantedDept)
                
            else:
                buildingAutoer.setBuildingType(quest.getBuildingTrack())

            buildingAutoer.start()

        elif quest.getType()==Quests.RecoverItemQuest:
            if quest.getHolder()==4:
                if quest.getLocation()==1:
                    if base.localAvatar.getZoneId()!=2000:
                        base.cr.playGame.getPlace().requestTeleport(2000,2000,None,None)
                        self.status='Fishing'
                    else:
                        self.status='Fishing'
                        self.checkWhatToDo()

                else:
                    if base.localAvatar.getZoneId()!=quest.getLocation():
                        base.cr.playGame.getPlace().requestTeleport(quest.getLocation(),quest.getLocation(),None,None)
                        self.status='Fishing'
                    else:
                        self.status='Fishing'
                        self.checkWhatToDo()
                        
            elif quest.getHolder() == 'rb':
                    cfoMaxer.otherFunctions.onlyLast=False
                    cfoMaxer.mintAutoer.setType(12500)
                    cfoMaxer.otherFunctions.onlyDoMint()
                    cfoMaxer.otherFunctions.start()
                    
            elif quest.getHolder() == 'tbc':
                    ceoMaxer.otherFunctions.start()
                    
            else:
                buildingAutoer.clearSettings()
                gagTrainer.clearSettings()
                if not self.isSuitOnlyBldg(quest.getHolder()) or quest.getHolderType()=='track':
                    if quest.getLocation()==1:
                        if type(quest.getHolder())==int:
                            gagTrainer.setLocation(self.getBestZoneForCogLevel(quest.getHolder()+1))
                        elif quest.getHolderType()=='track':
                            gagTrainer.setLocation(2000)
                        else:   
                            optimalLoc = self.optimalSuitLocations.get(quest.getHolder(), self.getBestZoneForCogLevel(self.getCogLevelFromCog(quest.getHolder())+1))
                            gagTrainer.setLocation(optimalLoc)
                    else:
                        wantedLoc = quest.getLocation()
                        if wantedLoc == 11000:
                            wantedLoc = 11200
                            
                        gagTrainer.setLocation(wantedLoc)

                    if type(quest.getHolder())==int:
                        gagTrainer.setCogLevel(quest.getHolder())
                    elif quest.getHolderType()=='track':
                        gagTrainer.setCogType(quest.getHolder())
                    else:
                        gagTrainer.setCogName(self.getSuitName(quest.getHolder()))
                    gagTrainer.start()

                elif quest.getLocation()==12000:
                    cfoMaxer.otherFunctions.onlyLast=True
                    cfoMaxer.otherFunctions.onlyDoMint()
                    cfoMaxer.mintAutoer.setType(12500)
                    cfoMaxer.otherFunctions.start()

                elif quest.getLocation()==11000:
                    vpMaxer.otherFunctions.onlyLast=True
                    vpMaxer.otherFunctions.onlyDoFactory()
                    vpMaxer.otherFunctions.start()

                else:
                    if quest.getLocation()==1:
                        buildingAutoer.setLocation(self.getBestZoneForBuildingLevel(4))
                        buildingAutoer.setNumFloors(4)
                        buildingAutoer.shouldChangeHood = True
                    else:
                        buildingAutoer.setLocation(quest.getLocation())
                    if quest.getHolder()==1:
                        buildingAutoer.setBuildingType('')
                    else:
                        buildingAutoer.setBuildingType(self.getSuitDepartment(quest.getHolder()))
                    buildingAutoer.start()

        elif quest.getType()==Quests.DeliverGagQuest:
            Sequence(Func(gagTrainer.restock.restockGags,quest.getGagType()),Wait(2),Func(self.doNPCTask, False, idx)).start()

        elif quest.getType()==Quests.SkelecogLevelQuest:
            if quest.getLocation()==11000:
                vpMaxer.otherFunctions.onlyLast=False
                vpMaxer.otherFunctions.onlyDoFactory()
                vpMaxer.otherFunctions.start()
            elif quest.getLocation()==12000:
                cfoMaxer.otherFunctions.onlyLast=False
                cfoMaxer.mintAutoer.setType(12500)
                cfoMaxer.otherFunctions.onlyDoMint()
                cfoMaxer.otherFunctions.start()
            elif quest.getLocation()==13000:
                cjMaxer.otherFunctions.onlyDoDa()
                cjMaxer.otherFunctions.start()
            elif quest.getLocation()==1:
                if quest.getCogLevel()<9:
                    vpMaxer.otherFunctions.onlyLast=False
                    vpMaxer.otherFunctions.onlyDoFactory()
                    vpMaxer.otherFunctions.start()
                else:
                    cfoMaxer.otherFunctions.onlyLast=False
                    cfoMaxer.mintAutoer.setType(12500)
                    cfoMaxer.otherFunctions.onlyDoMint()
                    cfoMaxer.otherFunctions.start()

        elif quest.getType()==Quests.SkelecogQuest:
            if quest.getLocation()==11000:
                vpMaxer.otherFunctions.onlyLast=False
                vpMaxer.otherFunctions.onlyDoFactory()
                vpMaxer.otherFunctions.start()
            elif quest.getLocation()==12000:
                cfoMaxer.otherFunctions.onlyLast=False
                cfoMaxer.mintAutoer.setType(12500)
                cfoMaxer.otherFunctions.onlyDoMint()
                cfoMaxer.otherFunctions.start()
            elif quest.getLocation() in (12500,12600,12700):
                cfoMaxer.otherFunctions.onlyLast=False
                cfoMaxer.mintAutoer.setType(quest.getLocation())
                cfoMaxer.otherFunctions.onlyDoMint()
                cfoMaxer.otherFunctions.start()
            elif quest.getLocation()==13000:
                cjMaxer.otherFunctions.onlyDoDa()
                cjMaxer.otherFunctions.start()
            elif quest.getLocation()==1:
                if quest.getCogLevel()<9:
                    vpMaxer.otherFunctions.onlyLast=False
                    vpMaxer.otherFunctions.onlyDoFactory()
                    vpMaxer.otherFunctions.start()
                else:
                    cfoMaxer.otherFunctions.onlyLast=False
                    cfoMaxer.mintAutoer.setType(12500)
                    cfoMaxer.otherFunctions.onlyDoMint()
                    cfoMaxer.otherFunctions.start()

        elif quest.getType() in (Quests.FactoryQuest,Quests.ForemanQuest):
            vpMaxer.otherFunctions.onlyLast=True
            vpMaxer.otherFunctions.onlyDoFactory()
            vpMaxer.otherFunctions.start()

        elif quest.getType() in (Quests.SupervisorQuest,Quests.MintQuest):
            cfoMaxer.otherFunctions.onlyLast=True
            cfoMaxer.otherFunctions.onlyDoMint()
            cfoMaxer.mintAutoer.setType(quest.getLocation())
            cfoMaxer.otherFunctions.start()

        elif quest.getType()==Quests.SkeleReviveQuest:
            ceoMaxer.otherFunctions.start()

        elif quest.getType()==Quests.TrackChoiceQuest:
            self.doNPCTask(True, idx)

        elif quest.getType()==Quests.TrolleyQuest:
            self.doTrolleyTask()

        elif quest.getType() == Quests.PhoneQuest:
            base.localAvatar._LocalToon__handleClarabelleButton()

        elif quest.getType() == Quests.FriendQuest:
            self.doFriendTask()

        else:
            base.localAvatar.setSystemMessage(0, 'Unknown task')


    def isQuestComplete(self):
        completeList = []

        for i in range(len(base.localAvatar.quests)):
            questDesc = base.localAvatar.quests[i]

            quest = Quests.getQuest(base.localAvatar.quests[i][0])

            if quest.getCompletionStatus(base.localAvatar, questDesc) == Quests.COMPLETE:
                completeList.append(i)

        return completeList

    def isSuitOnlyBldg(self,suitType):
        try:
            if SuitBattleGlobals.SuitAttributes[suitType]['level']+1>6:
                return True
            else:
                return False
        except KeyError:
            return False
