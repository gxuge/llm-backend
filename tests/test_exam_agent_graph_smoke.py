def test_graph_import_smoke():
    from app.graphs.exam_agent_graph import get_exam_agent_graph

    graph = get_exam_agent_graph()
    assert graph is not None
