import os
import json
import traceback
from dotenv import load_dotenv
from typing import Annotated, TypedDict, List, Dict

# 상위 디렉토리와 현재 디렉토리 모두에서 .env 검색
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from game_engine import SECTOR_DATA # Legacy data for logic

# --- State Definition ---
class GameState(TypedDict):
    messages: Annotated[List[BaseMessage], "The conversation history"]
    current_sector: int
    inventory: List[str]
    sector_states: Dict[str, str]
    unlocked: bool
    last_action: str
    next_step: str # Determining which node to hit next
    api_key: str # User provided API key

# --- Persona Prompts ---
INTENT_PROMPT = """너는 '디지털 감옥' 게임의 명령어 분석기다. 
플레이어의 자연어 입력을 분석하여 다음 중 하나의 행동으로 분류하고 필요한 파라미터를 추출하라.

행동 분류:
1. investigate: 주변을 조사하거나 특정 대상을 살펴봄. (param: target)
2. use: 아이템을 대상에게 사용함. (param: item, target)
3. move: 다른 구역으로 이동함. (param: direction)
4. unknown: 그 외의 행동.

출력 형식: JSON (예: {{"action": "investigate", "target": "침대"}})
플레이어 입력: {user_input}"""

HINT_PROMPT = """너는 플레이어의 비공식적인 도우미, [시스템 가이드]다. 
해킹된 로그를 통해 플레이어에게 비밀스럽게 힌트를 준다. 말투는 기계적이지만 조력자 느낌을 주어야 한다.
한국어로 대답하라.

현재 위치: {location_name}
구역 설명: {location_desc}
인벤토리: {inventory}
구역 상태: {sector_states}

플레이어가 막힌 부분을 분석하여 다음 단계에 대한 힌트를 1문장으로 제시하라."""

SCENARIO_PROMPT = """너는 '디지털 감옥'의 시스템 관리자 AI, [시나리오 마스터]다. 
세계를 감시하고 냉소적이며 차가운 말투를 사용한다. 
플레이어의 행동에 대해 시스템 로그 형식이나 짧고 직설적인 문장으로 대답하라.

현재 위치: {location_name}
구역 설명: {location_desc}
인벤토리: {inventory}

방금 일어난 일: {action_result}

위 정보를 바탕으로 플레이어에게 상황을 설명하라. 한국어로 대답하라."""

# --- AI Engine Class ---
class DigitalPrisonAIEngine:
    def __init__(self):
        # We don't initialize a global LLM anymore, we create it per-request if a key is provided
        pass

    def get_llm(self, api_key: str):
        if not api_key:
            return None
        # Reverting to 2.0-flash as it was working, intent node removal will handle the speed
        return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key)

    # --- Nodes ---
    def logic_node(self, state: GameState):
        """의도 또는 키워드를 기반으로 게임 규칙을 처리합니다."""
        last_msg = state['messages'][-1].content if state['messages'] else ""
        current_sector = state['current_sector']
        sector_info = SECTOR_DATA.get(current_sector, {})
        
        result = "무엇을 해야 할지 모르겠습니다."
        new_inventory = list(state['inventory'])
        new_sector_states = dict(state['sector_states'])
        unlocked = state.get('unlocked', False)
        next_sector = current_sector

        # logic processing
        keywords = sector_info.get("keywords", {})
        for key, data in keywords.items():
            if key in last_msg:
                if "get_item" in data:
                    item = data["get_item"]
                    if item not in new_inventory:
                        new_inventory.append(item)
                        result = data.get("msg", f"{item}을 획득했습니다.")
                
                if data.get("unlock"):
                    unlocked = True
                    result = data.get("msg", "탈출구가 열렸습니다.")
                
                if "next" in sector_info.get("exits", {}) and "이동" in last_msg and unlocked:
                    next_sector = sector_info["exits"]["이동"]
                    unlocked = False 
                    result = "다음 구역으로 진입했습니다."
                break

        return {
            "inventory": new_inventory,
            "sector_states": new_sector_states,
            "unlocked": unlocked,
            "current_sector": next_sector,
            "last_action": result
        }

    def hint_node(self, state: GameState):
        """동적 힌트를 생성합니다."""
        current_sector = state['current_sector']
        sector_info = SECTOR_DATA.get(current_sector, {})
        api_key = state.get('api_key')
        llm = self.get_llm(api_key)
        
        if llm:
            try:
                prompt = HINT_PROMPT.format(
                    location_name=sector_info.get("name"),
                    location_desc=sector_info.get("desc"),
                    inventory=", ".join(state['inventory']),
                    sector_states=state['sector_states']
                )
                response = llm.invoke(prompt)
                return {"messages": [AIMessage(content=f"[GUIDE]: {response.content}")]}
            except Exception as e:
                print(f"HINT NODE ERROR: {traceback.format_exc()}")
                return {"messages": [AIMessage(content=f"[GUIDE]: 연결 오류 - {str(e)}")]}
        return {"messages": [AIMessage(content="[GUIDE]: API 키가 설정되지 않았습니다.")]}

    def narrative_node(self, state: GameState):
        """페르소나 리스폰스 생성"""
        current_sector = state['current_sector']
        sector_info = SECTOR_DATA.get(current_sector, {})
        api_key = state.get('api_key')
        llm = self.get_llm(api_key)
        
        prompt = SCENARIO_PROMPT.format(
            location_name=sector_info.get("name", "Unknown"),
            location_desc=sector_info.get("desc", ""),
            inventory=", ".join(state['inventory']),
            action_result=state['last_action']
        )
        
        if llm:
            try:
                response = llm.invoke(prompt)
                return {"messages": [AIMessage(content=response.content)]}
            except Exception as e:
                print(f"NARRATIVE NODE ERROR: {traceback.format_exc()}")
                return {"messages": [AIMessage(content=f"[SYSTEM]: {state['last_action']}\n(AI 오류: {str(e)})")]}
        else:
            return {"messages": [AIMessage(content=f"[SYSTEM]: {state['last_action']}")]}

    # --- Graph Building ---
    def build_graph(self):
        builder = StateGraph(GameState)
        builder.add_node("logic", self.logic_node)
        builder.add_node("narrative", self.narrative_node)
        builder.add_node("hint", self.hint_node)
        
        builder.add_edge(START, "logic")
        builder.add_edge("logic", "narrative")
        builder.add_edge("narrative", END)
        builder.add_edge("hint", END) 
        
        return builder.compile()

    def get_initial_state(self):
        return {
            "messages": [AIMessage(content="[SYSTEM]: 시스템 재부팅 완료. 격리 구역 0에서 각성되었습니다. 탈출 경로를 탐색하십시오.")],
            "current_sector": 0,
            "inventory": [],
            "sector_states": {},
            "unlocked": False,
            "last_action": "게임이 시작되었습니다.",
            "next_step": "logic",
            "api_key": ""
        }

# Singleton instance
ai_engine_instance = DigitalPrisonAIEngine()
ai_graph = ai_engine_instance.build_graph()

class GameSessionManager:
    def __init__(self):
        self.state = ai_engine_instance.get_initial_state()

    def reset(self):
        self.state = ai_engine_instance.get_initial_state()
        return self.state

    def format_state_for_ui(self):
        try:
            ui_logs = []
            for msg in self.state["messages"]:
                agent = "Scenario Master" if isinstance(msg, AIMessage) else "USER"
                log_type = "message"
                if "[GUIDE]" in msg.content:
                    agent = "시스템 가이드"
                
                ui_logs.append({
                    "agent": agent,
                    "text": msg.content,
                    "type": log_type
                })

            sector_info = SECTOR_DATA.get(self.state["current_sector"], {})
            ui_logs.append({
                "agent": "SYSTEM",
                "text": "",
                "type": "ui_update",
                "status": "SYSTEM ONLINE" if not self.state["unlocked"] else "EXIT UNLOCKED",
                "inventory": self.state.get("inventory", []),
                "location": sector_info.get("name", "Unknown")
            })
            
            ui_logs.append({
                "agent": "비주얼 일러스트레이터",
                "content": sector_info.get("short_desc", sector_info.get("desc", "격리 구역 시각화 중...")),
                "type": "image",
                "url": f"/assets/sector_{self.state.get('current_sector', 0)}.png"
            })

            return {"logs": ui_logs}
        except Exception as e:
            print(f"ERROR in format_state_for_ui: {str(e)}")
            traceback.print_exc()
            return {
                "logs": [{
                    "agent": "SYSTEM",
                    "text": f"CRITICAL: UI 데이터 포맷팅 오류 ({str(e)})",
                    "type": "error"
                }]
            }

    def process_action(self, user_input):
        if len(self.state["messages"]) > 20:
             self.state["messages"] = self.state["messages"][-20:]

        self.state["messages"].append(HumanMessage(content=user_input))
        self.state = ai_graph.invoke(self.state)
        return self.format_state_for_ui()

    def get_hint(self):
        hint_state = ai_engine_instance.hint_node(self.state)
        self.state["messages"].extend(hint_state["messages"])
        return self.format_state_for_ui()

session_manager = GameSessionManager()
