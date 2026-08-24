from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class AnalysisState(TypedDict):
    company_name: str
    result: str


def analyze_company(state: AnalysisState) -> AnalysisState:
    return {
        **state,
        "result": f"{state['company_name']} 분석 준비 완료",
    }


def build_analysis_graph():
    graph = StateGraph(AnalysisState)

    graph.add_node(
        "analyze",
        analyze_company,
    )

    graph.add_edge(
        START,
        "analyze",
    )

    graph.add_edge(
        "analyze",
        END,
    )

    return graph.compile()