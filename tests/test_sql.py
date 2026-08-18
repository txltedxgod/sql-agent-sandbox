from sql_agent.agent import SQLAgent

def test_sql_generation_and_exec():
    ag = SQLAgent()
    sql = ag.natural_language_to_sql("Show total sales")
    res = ag.execute_query(sql)
    assert res["rows"][0][0] == 3900.0
