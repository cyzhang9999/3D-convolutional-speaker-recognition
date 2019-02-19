
def fetch_best(path):
    last_score = 0.0
    record = ""
    last_key = ""
    with open(path) as in_handler:
        for each_line in in_handler:
            each_line = each_line.strip()
            line_arr = each_line.split()
            predict = line_arr[0]
            label = line_arr[1]
            score = line_arr[2]
            if label != last_key:
                if last_key:
                    print(record)
                    last_key = label
                    last_score = score
                    record = each_line
                else:
                    last_key = label
                    last_score = score
                    record = each_line
            else:
                if score > last_score:
                    last_score = score
                    record = each_line
        print(record)

if __name__ == '__main__':
    path = "results/SCORES/score.log"
    fetch_best(path)