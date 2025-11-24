import nflreadpy as nfl

def main():
    rosters = nfl.load_rosters()
    print(len(rosters))
    # for roster in rosters.iter_rows(named=True):
    #     print(roster)


if __name__ == "__main__":
    main()