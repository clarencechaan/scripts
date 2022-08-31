import subprocess
import sys
import re
import math
from datetime import datetime


def main():
    pmset_lines = get_relevant_lines()
    fill_charge(pmset_lines)
    events = convert_lines(pmset_lines)
    print_events(events)
    stats = get_stats(events)
    print("----------------------------------------------------------------------")
    if stats["plug_date_time"]:
        print(
            f'Summary from {datetime_to_str(stats["unplug_date_time"])} to {datetime_to_str(stats["plug_date_time"])}:')
    else:
        print(
            f'Summary from {datetime_to_str(stats["unplug_date_time"])} to now:')
    print(
        f'Last charged to 100% on {datetime_to_str(stats["unplug_date_time"])}')
    if stats["plug_date_time"]:
        print(
            f'Plugged in to AC at {stats["plug_charge"]}% on {datetime_to_str(stats["plug_date_time"])}')
    print(f'\n{stats["drain_awake"]}% of battery used over {stats["time_awake_hours"]}h {stats["time_awake_minutes"]}min of active usage')
    print(f'{stats["drain_asleep"]}% of battery used over {stats["time_asleep_hours"]}h {stats["time_asleep_minutes"]}min of sleep')
    print('\nRate of Use:')
    print(
        f'{stats["rate_drain_awake"]:.2f}%/h of battery used during active usage')
    print(f'{stats["rate_drain_asleep"]:.2f}%/h of battery used during sleep')
    if stats["estimate_full_awake_hours"] or stats["estimate_full_awake_minutes"] or stats["estimate_time_left_hours"] or stats["estimate_time_left_minutes"]:
        print('\nEstimates:')
        print(
            f'{stats["estimate_full_awake_hours"]}h {stats["estimate_full_awake_minutes"]}min of active usage from full charge')
        print(
            f'{stats["estimate_time_left_hours"]}h {stats["estimate_time_left_minutes"]}min of active usage left from current charge')

    print("----------------------------------------------------------------------")


def get_stats(events):
    unplug_date_time = events[0]["date_time"]
    prev_date_time = None
    prev_charge = events[0]["charge"]
    current_charge = get_current_charge()
    time_awake = 0
    time_asleep = 0
    drain_awake = 0
    drain_asleep = 0
    prev_date_time = None
    awake = None
    rate_drain_awake = 0.00
    rate_drain_asleep = 0.00
    plugged = None
    plug_date_time = None
    plug_charge = None
    estimate_full_awake_time = 0
    estimate_time_left = 0
    estimate_full_awake_hours = 0
    estimate_full_awake_minutes = 0
    estimate_time_left_hours = 0
    estimate_time_left_minutes = 0

    for event in events:
        if plugged == True:
            break

        if prev_date_time != None and awake == False:
            time_asleep += (event["date_time"] -
                            prev_date_time).total_seconds()
            drain_asleep += prev_charge - event["charge"]
        if prev_date_time != None and awake == True:
            time_awake += (event["date_time"] - prev_date_time).total_seconds()
            drain_awake += prev_charge - event["charge"]

        if event["event_type"] == "PLUG":
            plugged = True
        elif event["event_type"] == "UNPLUG":
            plugged = False
        elif event["event_type"] == "WAKE":
            if awake == None:
                time_asleep += (event["date_time"] -
                                unplug_date_time).total_seconds()
                drain_asleep += prev_charge - event["charge"]
            awake = True
        elif event["event_type"] == "SLEEP":
            if awake == None:
                time_awake += (event["date_time"] -
                               unplug_date_time).total_seconds()
                drain_awake += prev_charge - event["charge"]
            awake = False

        prev_date_time = event["date_time"]
        prev_charge = event["charge"]

    if plugged == True:
        plug_date_time = prev_date_time
        plug_charge = prev_charge
    else:
        time_awake += (datetime.now() - prev_date_time).total_seconds()
        drain_awake += prev_charge - get_current_charge()

    time_awake_hours = int(time_awake // 3600)
    time_awake_minutes = int((time_awake % 3600) // 60)
    time_asleep_hours = int(time_asleep // 3600)
    time_asleep_minutes = int((time_asleep % 3600) // 60)

    if (time_awake / 3600):
        rate_drain_awake = math.floor(
            (drain_awake / (time_awake / 3600)) * 100) / 100
    if (time_asleep / 3600):
        rate_drain_asleep = math.floor(
            (drain_asleep / (time_asleep / 3600)) * 100) / 100

    if drain_awake > 0:
        estimate_full_awake_time = (100 / drain_awake) * time_awake
        estimate_time_left = (current_charge / drain_awake) * time_awake
        estimate_full_awake_hours = int(estimate_full_awake_time // 3600)
        estimate_full_awake_minutes = int(
            (estimate_full_awake_time % 3600) // 60)
        estimate_time_left_hours = int(estimate_time_left // 3600)
        estimate_time_left_minutes = int((estimate_time_left % 3600) // 60)

    return {"time_awake_hours": time_awake_hours,
            "time_awake_minutes": time_awake_minutes,
            "time_asleep_hours": time_asleep_hours,
            "time_asleep_minutes": time_asleep_minutes,
            "drain_awake": drain_awake,
            "drain_asleep": drain_asleep,
            "rate_drain_awake": rate_drain_awake,
            "rate_drain_asleep": rate_drain_asleep,
            "unplug_date_time": unplug_date_time,
            "plug_date_time": plug_date_time,
            "plug_charge": plug_charge,
            "current_charge": current_charge,
            "estimate_full_awake_hours": estimate_full_awake_hours,
            "estimate_full_awake_minutes": estimate_full_awake_minutes,
            "estimate_time_left_hours": estimate_time_left_hours,
            "estimate_time_left_minutes": estimate_time_left_minutes}


def get_pmset_log():
    raw_output = subprocess.check_output(["pmset", "-g", "log"])
    return str(raw_output, "utf-8") if sys.version_info.major >= 3 else raw_output


def get_current_charge():
    raw_output = subprocess.check_output(["pmset", "-g", "ps"])
    string = str(
        raw_output, "utf-8") if sys.version_info.major >= 3 else raw_output
    charge_int = int(re.search(r'\t(.*?)%', string).group(1))
    return charge_int


def get_relevant_lines():
    lines = get_pmset_log().splitlines()
    lines.reverse()
    unplug_index = list(
        "Summary- [System: " in line and " Using Batt" in line for line in lines).index(True)
    unplug_index = next(i for i, line in enumerate(
        lines) if "Summary- [System: " in line and " Using Batt" in line and get_line_charge(line) == 100)
    lines = lines[:unplug_index + 1]
    lines.reverse()
    return lines


def convert_lines(lines):
    converted = []
    for line in lines:
        event = unplug_event(line) or wake_event(
            line) or plug_event(line) or sleep_event(line)
        if (event):
            converted.append(event)
    return converted


def unplug_event(line):
    if "Summary- [System: " in line and " Using Batt" in line and get_line_charge(line) == 100:
        date_time = get_line_date_time(line)
        charge = get_line_charge(line)
        unplug_event = {"event_type": "UNPLUG",
                        "date_time": date_time, "charge": charge, "line": line}
        return unplug_event
    pass


def wake_event(line):
    if " Wake  " in line:
        date_time = get_line_date_time(line)
        charge = get_line_charge(line)
        wake_event = {"event_type": "WAKE",
                      "date_time": date_time, "charge": charge, "line": line}
        return wake_event
    pass


def plug_event(line):
    if "Summary- [System: " in line and "Using AC" in line:
        date_time = get_line_date_time(line)
        charge = get_line_charge(line)
        plug_event = {"event_type": "PLUG",
                      "date_time": date_time, "charge": charge, "line": line}
        return plug_event
    pass


def sleep_event(line):
    if "Entering Sleep state" in line:
        date_time = get_line_date_time(line)
        charge = get_line_charge(line)
        sleep_event = {"event_type": "SLEEP",
                       "date_time": date_time, "charge": charge, "line": line}
        return sleep_event
    pass


# infer charge values for lines that are cut off
def fill_charge(lines):
    for idx, line in enumerate(lines):
        if "(Charge:" not in line or ")" not in line:
            prev_idx = idx - 1
            while "(Charge:" not in lines[prev_idx] or ")" not in lines[prev_idx]:
                prev_idx -= 1
            lines[idx] = lines[idx].split("(", 1)[0] + "(Charge: " + \
                str(get_line_charge(lines[prev_idx])) + ")"


def print_events(events):
    for event in events:
        date_time = event["date_time"]
        event_type = event["event_type"]
        charge = str(event.get("charge")) + "%"
        line = event["line"]


def get_line_date_time(line):
    date_time_str = line[:19]
    date_time_obj = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')
    return date_time_obj


def get_line_charge(line):
    return int(re.search(r'Charge:\s?(.*?)%?\)', line).group(1))


def datetime_to_str(date_time):
    return date_time.strftime("%B %d, %Y at %-I:%M %p")


if __name__ == "__main__":
    main()
    sys.exit(0)
