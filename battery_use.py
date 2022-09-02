import subprocess
import sys
import re
import math
from datetime import datetime


def main():
    pmset_lines = get_pmset_log().splitlines()
    lines = get_relevant_lines(pmset_lines)
    events = convert_lines(lines)
    print_events(events)
    stats = get_stats(events)

    print("----------------------------------------------------------------------")
    if stats["plugged"] and stats["current_charge"] == 100:
        print(f'Fully charged (100%)')
    elif stats["plugged"]:
        print(f'Charging ({stats["current_charge"]}%)')
    else:
        print(f'On battery ({stats["current_charge"]}%)')
    print(f'\nSummary:')
    print(
        f'Last charged to 100% on {datetime_to_str(stats["full_unplug_date_time"])}')
    if stats["plugged"]:
        print(
            f'Plugged in to AC at {stats["plug_charge"]}% on {datetime_to_str(stats["plug_date_time"])}')
        print(f'\nSince plugged in ({stats["plug_time_ago_str"]} ago):')
        if stats["current_charge"] == 100:
            print(f'{stats["charge_gain"]}% of battery charged')
        else:
            print(
                f'{stats["charge_gain"]}% of battery charged over {stats["plug_time_ago_str"]}')
            print("\nRate of Charge:")
            print(f'{stats["rate_charge"]:.2f}%/h of battery charged')
            if stats["charge_gain"] >= 5:
                print('\nEstimates:')
                print(
                    f'{stats["estimate_full_charge_time_str"].rjust(9)} to charge from 0% to 100%')
                print(
                    f'{stats["estimate_charge_time_left_str"].rjust(9)} until fully charged')

    else:
        print(
            f'Last unplugged from AC at {stats["latest_unplug_charge"]}% on {datetime_to_str(stats["latest_unplug_date_time"])}')
        print(f'\nSince unplug ({stats["unplug_time_ago_str"]} ago):')
        print(
            f'{stats["drain_awake"]}% of battery used over {stats["time_awake_str"]} of active usage')
        print(
            f'{stats["drain_asleep"]}% of battery used over {stats["time_asleep_str"]} of sleep')
        print('\nRate of Use:')
        print(
            f'{stats["rate_drain_awake"]:.2f}%/h of battery used during active usage')
        print(
            f'{stats["rate_drain_asleep"]:.2f}%/h of battery used during sleep')
        if stats["drain_awake"] >= 5:
            print('\nEstimates:')
            print(
                f'{stats["estimate_full_awake_time_str"].rjust(9)} of active usage from full charge')
            print(
                f'{stats["estimate_time_left_str"].rjust(9)} of active usage left from current charge')

    print("----------------------------------------------------------------------")


def get_stats(events):
    full_unplug_date_time = events[0]["date_time"]
    latest_unplug_date_time = full_unplug_date_time
    latest_unplug_charge = events[0]["charge"]
    prev_date_time = None
    prev_charge = events[0]["charge"]
    current_charge = get_current_charge()
    time_awake = 0
    time_asleep = 0
    drain_awake = 0
    drain_asleep = 0
    time_since_plug = 0
    prev_date_time = None
    awake = isFirstAwake(events)
    rate_drain_awake = 0.00
    rate_drain_asleep = 0.00
    rate_charge = 0.00
    plugged = False
    plug_date_time = None
    plug_charge = None
    plug_time_ago_str = None
    charge_gain = 0
    estimate_full_awake_time = 0
    estimate_time_left = 0
    estimate_full_charge_time = 0
    estimate_charge_time_left = 0
    estimate_full_awake_time_str = ""
    estimate_time_left_str = ""
    estimate_full_charge_time_str = ""
    estimate_charge_time_left_str = ""

    for event in events:
        print(event["event_type"], event["line"])
        if prev_date_time != None and awake == False:
            time_asleep += (event["date_time"] -
                            prev_date_time).total_seconds()
            drain_asleep += prev_charge - event["charge"]
        if prev_date_time != None and awake == True:
            time_awake += (event["date_time"] - prev_date_time).total_seconds()
            drain_awake += prev_charge - event["charge"]

        if event["event_type"] == "PLUG" and not plugged:
            plug_date_time = event["date_time"]
            plug_charge = event["charge"]
            plugged = True
        elif event["event_type"] == "UNPLUG" and plugged:
            latest_unplug_date_time = event["date_time"]
            latest_unplug_charge = event["charge"]
            time_awake = 0
            time_asleep = 0
            drain_awake = 0
            drain_asleep = 0
            plugged = False
        elif event["event_type"] == "WAKE":
            if awake == None:
                time_asleep += (event["date_time"] -
                                latest_unplug_date_time).total_seconds()
                drain_asleep += prev_charge - event["charge"]
            awake = True
        elif event["event_type"] == "SLEEP":
            if awake == None:
                time_awake += (event["date_time"] -
                               latest_unplug_date_time).total_seconds()
                drain_awake += prev_charge - event["charge"]
            awake = False

        prev_date_time = event["date_time"]
        prev_charge = event["charge"]

    if plugged:
        plug_time_ago_str = date_diff_str(plug_date_time, datetime.now())
        time_since_plug = (datetime.now() - plug_date_time).total_seconds()
        charge_gain = current_charge - plug_charge

    time_awake += (datetime.now() - prev_date_time).total_seconds()
    drain_awake += prev_charge - get_current_charge()

    time_awake_str = duration_str(time_awake)
    time_asleep_str = duration_str(time_asleep)

    if not plugged and time_awake / 3600:
        rate_drain_awake = math.floor(
            (drain_awake / (time_awake / 3600)) * 100) / 100
    if not plugged and time_asleep / 3600:
        rate_drain_asleep = math.floor(
            (drain_asleep / (time_asleep / 3600)) * 100) / 100
    if plugged and time_since_plug:
        rate_charge = math.floor(
            (charge_gain / (time_since_plug / 3600)) * 100) / 100

    if drain_awake >= 5:
        estimate_full_awake_time = (100 / drain_awake) * time_awake
        estimate_time_left = (current_charge / drain_awake) * time_awake
        estimate_full_awake_time_str = duration_str(estimate_full_awake_time)
        estimate_time_left_str = duration_str(estimate_time_left)
    if charge_gain >= 5:
        estimate_full_charge_time = (100 / charge_gain) * time_since_plug
        estimate_charge_time_left = (
            (100 - current_charge) / charge_gain) * time_since_plug
        estimate_full_charge_time_str = duration_str(estimate_full_charge_time)
        estimate_charge_time_left_str = duration_str(estimate_charge_time_left)

    unplug_time_ago_str = date_diff_str(
        latest_unplug_date_time, datetime.now())

    return {"time_awake_str": time_awake_str,
            "time_asleep_str": time_asleep_str,
            "drain_awake": drain_awake,
            "drain_asleep": drain_asleep,
            "rate_drain_awake": rate_drain_awake,
            "rate_drain_asleep": rate_drain_asleep,
            "full_unplug_date_time": full_unplug_date_time,
            "latest_unplug_date_time": latest_unplug_date_time,
            "unplug_time_ago_str": unplug_time_ago_str,
            "latest_unplug_charge": latest_unplug_charge,
            "plug_date_time": plug_date_time,
            "plug_charge": plug_charge,
            "plug_time_ago_str": plug_time_ago_str,
            "charge_gain": charge_gain,
            "current_charge": current_charge,
            "estimate_full_awake_time_str": estimate_full_awake_time_str,
            "estimate_time_left_str": estimate_time_left_str,
            "rate_charge": rate_charge,
            "estimate_full_charge_time_str": estimate_full_charge_time_str,
            "estimate_charge_time_left_str": estimate_charge_time_left_str,
            "plugged": plugged}


def isFirstAwake(events):
    awake = True
    for event in events:
        if event["event_type"] == "SLEEP":
            awake = True
            break
        elif event["event_type"] == "AWAKE":
            awake = False
            break
    return awake


def date_diff_str(date1, date2):
    seconds = abs(date1 - date2).total_seconds()
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    string = ""
    if hours > 0:
        string += f'{hours}h '
    string += f'{minutes}min'
    return string


def duration_str(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    string = ""
    if hours > 0:
        string += f'{hours}h '
    string += f'{minutes}min'
    return string


def get_pmset_log():
    raw_output = subprocess.check_output(["pmset", "-g", "log"])
    return str(raw_output, "utf-8") if sys.version_info.major >= 3 else raw_output


def get_current_charge():
    raw_output = subprocess.check_output(["pmset", "-g", "ps"])
    string = str(
        raw_output, "utf-8") if sys.version_info.major >= 3 else raw_output
    charge_int = int(re.search(r'\t(.*?)%', string).group(1))
    return charge_int


def get_relevant_lines(lines):
    fill_charge(lines)
    lines.reverse()
    # get index of the oldest of the most recent set of 100% unplug lines
    full_unplug_index = None
    for idx, line in enumerate(lines):
        if "Summary- [System: " in line and " Using Batt" in line and get_line_charge(line) == 100:
            full_unplug_index = idx
        if full_unplug_index != None and get_line_charge(line) < 100:
            break
    lines = lines[:full_unplug_index + 1]
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
    if "Summary- [System: " in line and " Using Batt" in line:
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
