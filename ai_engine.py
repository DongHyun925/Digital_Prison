import os
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
# ... (prompts unchanged) ...

# --- AI Engine Class ---
class DigitalPrisonAIEngine:
    def __init__(self):
        # We don't initialize a global LLM anymore, we create it per-request if a key is provided
        pass

    def get_llm(self, api_key: str):
        if not api_key:
            return None
        return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key)

    # --- Nodes ---
    def intent_node(self, state: GameState):
        """플레이어의 의도를 분석합니다."""
        # For now, logic is static, but we keep the structure
        return {"next_step": "logic"}

    def logic_node(self, state: GameState):
        """의도 또는 키워드를 기반으로 게임 규칙을 처리합니다."""
        last_msg = state['messages'][-1].content if state['messages'] else ""
        current_sector = state['current_sector']
        sector_info = SECTOR_DATA.get(current_sector, {})
        
        result = "무엇을 해야 할지 모르겠습니다."
        new_inventory = list(state['inventory'])
        new_sector_states = dict(state['sector_states'])
        unlocked = state['unlocked']
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
            "last_action": result,
            "next_step": "narrative"
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
                print(f"HINT NODE ERROR: {str(e)}")
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    return {"messages": [AIMessage(content="[GUIDE]: 시스템이 과부하 상태입니다. 잠시 후 다시 시도해 주십시오.")]}
                return {"messages": [AIMessage(content=f"[GUIDE]: 연결 오류 - {str(e)}")]}
        return {"messages": [AIMessage(content="[GUIDE]: API 키가 설정되지 않았습니다. 상단에서 키를 입력해 주세요.")]}

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
                print(f"NARRATIVE NODE ERROR: {str(e)}")
                fallback_msg = f"[SYSTEM]: {state['last_action']}\n(시스템 연산 오류: {str(e)})"
                return {"messages": [AIMessage(content=fallback_msg)]}
        else:
            msg = f"[SYSTEM]: {state['last_action']}\n[NOTICE]: AI 기능이 비활성화 상태입니다. (API 키 미설정)"
            return {"messages": [AIMessage(content=msg)]}

    # --- Graph Building ---
    def build_graph(self):
        builder = StateGraph(GameState)
        builder.add_node("intent", self.intent_node)
        builder.add_node("logic", self.logic_node)
        builder.add_node("narrative", self.narrative_node)
        builder.add_node("hint", self.hint_node)
        
        builder.add_edge(START, "intent")
        builder.add_edge("intent", "logic")
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
            "inventory": self.state["inventory"],
            "location": sector_info.get("name", "Unknown")
        })
        
        ui_logs.append({
            "agent": "비주얼 일러스트레이터",
            "content": sector_info.get("short_desc", sector_info.get("desc")),
            "type": "image",
            "url": f"/assets/sector_{self.state['current_sector']}.png"
        })

        return {"logs": ui_logs}

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
