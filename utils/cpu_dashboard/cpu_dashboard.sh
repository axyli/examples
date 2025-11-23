#!/bin/bash

history_len=5  # скользящее среднее

declare -a core0_hist
declare -a core1_hist
declare -a package_hist

colorize() {
    local temp=$1
    local bar=$2
    if [ $temp -ge 80 ]; then
        echo -e "\033[1;31m$bar\033[0m"
    elif [ $temp -ge 60 ]; then
        echo -e "\033[1;33m$bar\033[0m"
    else
        echo -e "\033[1;32m$bar\033[0m"
    fi
}

make_bar() {
    local value=$1
    local max_len=30
    local len=$(( value * max_len / 100 ))
    printf "%-${max_len}s" "$(head -c $len < /dev/zero | tr '\0' '#')"
}

avg() {
    local arr=("$@")
    local sum=0
    for val in "${arr[@]}"; do sum=$((sum + val)); done
    echo $((sum / ${#arr[@]}))
}

while true; do
    # получаем температуру Core и Package
    read package core0 core1 <<<$(sensors | awk '/Package id 0/ {p=$4+0} /Core 0/ {c0=$3+0} /Core 1/ {c1=$3+0} END {print p, c0, c1}')

    # обновляем историю
    package_hist+=($package)
    core0_hist+=($core0)
    core1_hist+=($core1)

    if [ ${#package_hist[@]} -gt $history_len ]; then
        package_hist=("${package_hist[@]:1}")
        core0_hist=("${core0_hist[@]:1}")
        core1_hist=("${core1_hist[@]:1}")
    fi

    # скользящее среднее
    avg_package=$(avg "${package_hist[@]}")
    avg_core0=$(avg "${core0_hist[@]}")
    avg_core1=$(avg "${core1_hist[@]}")

    # частоты CPU
    freq0=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null)
    freq1=$(cat /sys/devices/system/cpu/cpu1/cpufreq/scaling_cur_freq 2>/dev/null)
    freq0=$((freq0/1000))
    freq1=$((freq1/1000))

    clear
    echo "CPU Dashboard – температура + частота (скользящее среднее, последние $history_len замера)"

    echo -n "Package: "
    colorize $avg_package "$(make_bar $avg_package) $avg_package°C"

    echo -n "Core 0:  "
    colorize $avg_core0 "$(make_bar $avg_core0) $avg_core0°C | $freq0 MHz"

    echo -n "Core 1:  "
    colorize $avg_core1 "$(make_bar $avg_core1) $avg_core1°C | $freq1 MHz"

    sleep 1
done
