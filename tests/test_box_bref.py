from max_pf.box_bref import (
    PlayerBox,
    build_id_map,
    normalize_name,
    parse_day_index,
    parse_game_lines,
)
from max_pf.models import PlayerLine

GAME_HTML = """
<table id="box-BOS-game-basic"><tbody>
<tr><th data-append-csv="tatumja01"><a>Jayson Tatum</a></th>
  <td data-stat="mp">35:00</td><td data-stat="fg">10</td><td data-stat="fga">20</td>
  <td data-stat="fg3">3</td><td data-stat="ft">5</td><td data-stat="fta">6</td>
  <td data-stat="trb">8</td><td data-stat="ast">5</td><td data-stat="stl">1</td>
  <td data-stat="blk">2</td><td data-stat="tov">3</td><td data-stat="pts">28</td></tr>
<tr><th data-append-csv="benchwa01"><a>Bench Warmer</a></th>
  <td data-stat="reason">Did Not Play</td></tr>
<tr class="thead"><th>Reserves</th></tr>
</tbody></table>
"""


def test_parse_game_lines_extracts_real_makes_attempts_and_skips_dnp():
    boxes = parse_game_lines(GAME_HTML)
    assert len(boxes) == 1  # DNP and subheader rows skipped
    pb = boxes[0]
    assert pb.bref_id == "tatumja01" and pb.team == "BOS"
    assert pb.line.pts == 28 and pb.line.tpm == 3 and pb.line.to == 3
    assert pb.line.fgm == 10 and pb.line.fga == 20
    assert abs(pb.line.fg_pct - 0.5) < 1e-9          # exact, no estimator
    assert abs(pb.line.ft_pct - 5 / 6) < 1e-9


def test_parse_day_index():
    html = 'x <a href="/boxscores/202512010BRK.html">a</a> <a href="/boxscores/202512010LAL.html">b</a> dup /boxscores/202512010BRK.html'
    assert parse_day_index(html) == ["/boxscores/202512010BRK.html", "/boxscores/202512010LAL.html"]


def test_normalize_name():
    assert normalize_name("Tatum,Jayson") == "jayson tatum"
    assert normalize_name("Luka Dončić") == "luka doncic"
    assert normalize_name("Jaren Jackson Jr.") == "jaren jackson"
    assert normalize_name("P.J. Tucker") == "pj tucker"


def test_build_id_map_matches_unmatched_and_ambiguous():
    bref = [
        PlayerBox("tatumja01", "Jayson Tatum", "BOS", PlayerLine()),
        PlayerBox("smithja01", "Jabari Smith", "HOU", PlayerLine()),
        PlayerBox("smithja02", "Jabari Smith", "PHO", PlayerLine()),  # duplicate name
    ]
    fantrax = {"s1": "Jayson Tatum", "s2": "Nobody Here", "s3": "Jabari Smith"}
    res = build_id_map(fantrax, bref)
    assert res.mapping == {"s1": "tatumja01"}
    assert res.unmatched == ["Nobody Here"]
    assert res.ambiguous == ["Jabari Smith"]
    assert 0.0 < res.coverage < 1.0


def test_build_id_map_applies_nickname_aliases():
    bref = [PlayerBox("carrila01", "Bub Carrington", "WAS", PlayerLine())]
    fantrax = {"s9": "Carlton Carrington"}
    res = build_id_map(fantrax, bref)  # uses default ALIASES
    assert res.mapping == {"s9": "carrila01"}
