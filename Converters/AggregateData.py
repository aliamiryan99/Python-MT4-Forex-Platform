from Converters.Tools import *
import copy


def aggregate_data(histories, time_frame):
    old_id = get_time_id(histories[0]['Time'], time_frame)
    new_history = []
    new_history.append(copy.deepcopy(histories[0]))
    for i in range(1, len(histories)):
        new_id = get_time_id(histories[i]['Time'], time_frame)
        if new_id != old_id:
            new_history.append(copy.deepcopy(histories[i]))
            old_id = new_id
        else:
            new_history[-1]['High'] = max(new_history[-1]['High'], histories[i]['High'])
            new_history[-1]['Low'] = min(new_history[-1]['Low'], histories[i]['Low'])
            new_history[-1]['Close'] = histories[i]['Close']
            new_history[-1]['Volume'] += histories[i]['Volume']
    return new_history

category = "Metal"
symbol = "XAUUSD"
time_frame_source = "H1"
time_frame_target = "H4"

data = read_data(category, symbol, time_frame_source)

target_data = aggregate_data(data, time_frame_target)

save_data(target_data, category, symbol, time_frame_target)

print("Completed")
