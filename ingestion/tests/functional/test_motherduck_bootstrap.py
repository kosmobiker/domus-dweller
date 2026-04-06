from unittest.mock import MagicMock, patch

from domus_dweller.sinks.motherduck_bootstrap import bootstrap_motherduck


def test_bootstrap_motherduck_executes_expected_sqls() -> None:
    # Given
    mock_con = MagicMock()
    
    # When
    with patch("duckdb.connect", return_value=mock_con), \
         patch("os.getenv", return_value="fake-token"):
        bootstrap_motherduck(database="test_db")
    
    # Then
    assert mock_con.execute.called
    calls = [call.args[0] for call in mock_con.execute.call_args_list]
    
    # Check for bronze schema creation
    assert any("CREATE SCHEMA IF NOT EXISTS bronze" in sql for sql in calls)
    
    # Check for bronze tables creation
    assert any("CREATE TABLE IF NOT EXISTS bronze.rent_bronze" in sql for sql in calls)
    assert any("CREATE TABLE IF NOT EXISTS bronze.sale_bronze" in sql for sql in calls)
    
    # Ensure NO silver or gold
    for sql in calls:
        assert "silver" not in sql.lower()
        assert "gold" not in sql.lower()
