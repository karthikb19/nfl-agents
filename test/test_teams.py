import nflreadpy as nfl

def main():
    players = nfl.load_players()
    s = set()
    for player in players.iter_rows(named=True):
        s.add(player["gsis_id"])
    print(len(s) == len(players))
if __name__ == "__main__":
    main()