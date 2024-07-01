#!/usr/bin/env python
import math
import matplotlib.pyplot as plt


class Motor:
    def torque(self, rpm):
        raise NotImplementedError

    def power(self, rpm):
        # Returns kW
        return self.torque(rpm) * math.pi * rpm / 30 / 1000


class EVMotor(Motor):
    def __init__(self, max_power, max_torque, max_power_rpm, max_rpm):
        self.max_power = max_power
        self.max_torque = max_torque
        self.max_power_rpm = max_power_rpm
        self.max_rpm = max_rpm

    def torque(self, rpm):
        if rpm < self.max_power_rpm:
            return self.max_torque  # in max torque part of the graph
        elif rpm > self.max_rpm:
            return 0  # excess rpm
        else:
            return (
                (self.max_rpm - rpm)
                / (self.max_rpm - self.max_power_rpm)
                * self.max_torque
            )


class KonaMotor(EVMotor):
    def __init__(self):
        super().__init__(151, 395, 3600, 10500)


class D4D1KD(Motor):
    # rpm to torque, according to
    # https://www.4x4community.co.za/forum/showthread.php/10949-2-5-D4D-vs-3-0-D4D
    _T = [
        (1000, 310),
        (1200, 343),
        (3300, 343),
        (3500, 325),
        (5000, 90),
    ]

    def __init__(self):
        pass

    def torque(self, rpm):
        for (a_r, a_t), (b_r, b_t) in zip(self._T, self._T[1:]):
            if a_r <= rpm <= b_r:
                r = (rpm - a_r) / (b_r - a_r)
                return (r * b_t) + ((1 - r) * a_t)
        return 0


class Wheel:
    def __init__(self, width, aspect_pct, wheel_size_in):
        self.width = width
        assert 1 <= aspect_pct <= 100
        self.aspect = aspect_pct / 100
        self.wheel_diameter_mm = wheel_size_in * 25.4

    def tyre_diameter(self):
        return (self.wheel_diameter_mm / 2 + (self.width * self.aspect)) / 1000

    def road_speed(self, wheel_rpm):
        # returns kph
        return (3.6 * wheel_rpm * math.pi * self.tyre_diameter()) / 30

    def wheel_rpm(self, road_speed_kph):
        return (30 * road_speed_kph) / (3.6 * math.pi * self.tyre_diameter())


class Vehicle:
    def __init__(self, engine, wheel, gears, final_drive):
        self.engine = engine
        self.wheel = wheel
        self.gears = gears
        self.final_drive = final_drive

    def select_gear(self, kph):
        # Return a 0-based index of which gear to choose for a given speed
        # gear chosen based on the maximum wheel torque for that gear
        wheel_rpm = self.wheel.wheel_rpm(kph)
        driveshaft_rpm = wheel_rpm * self.final_drive

        def get_torque(g_ratio):
            engine_rpm = driveshaft_rpm * g_ratio
            return self.engine.torque(engine_rpm) * g_ratio * self.final_drive

        # for (g, g_r) in enumerate(self.gears):
        #    print(g, g_r, driveshaft_rpm * g_r, get_torque(g_r))

        return max((get_torque(g_r), g) for (g, g_r) in enumerate(self.gears))[1]

    def wheel_torque(self, kph):
        # Return the torque at the wheels for a given speed, assuming best
        # gear selected
        wheel_rpm = self.wheel.wheel_rpm(kph)
        driveshaft_rpm = wheel_rpm * self.final_drive
        gear = self.select_gear(kph)
        engine_rpm = driveshaft_rpm * self.gears[gear]
        return self.engine.torque(engine_rpm) * self.gears[gear] * self.final_drive

    def torque_data(self):
        # making use of implicit x axis of len(ys)
        return [self.wheel_torque(kph) for kph in range(0, 121)]

    def gear_data(self):
        # making use of implicit x axis of len(ys)
        return [self.select_gear(kph) for kph in range(0, 121)]


stock_wheels = Wheel(205, 70, 15)
stock_hilux = Vehicle(
    D4D1KD(), stock_wheels, [4.313, 2.330, 1.436, 1.000, 0.838], 3.583
)

kona_wheels = Wheel(215, 55, 17)
kona = Vehicle(KonaMotor(), kona_wheels, [1.0], 7.981)

conv_hilux_3rd = Vehicle(KonaMotor(), stock_wheels, [1.436], 3.583)
conv_hilux_2nd = Vehicle(KonaMotor(), stock_wheels, [2.330], 3.583)
conv_hilux_3rd_41diff = Vehicle(KonaMotor(), stock_wheels, [1.436], 4.1)

fig, ax = plt.subplots()

handles = (ax.plot(kona.torque_data(), label="Kona Electric") +
           ax.plot(stock_hilux.torque_data(), label="Stock Hilux 3.0 D4D, 5sp manual") +
           ax.plot(conv_hilux_2nd.torque_data(), label="Electric Hilux, fixed 2nd") +
           ax.plot(conv_hilux_3rd.torque_data(), label="Electric Hilux, fixed 3rd") +
           ax.plot(conv_hilux_3rd_41diff.torque_data(), label="Electric Hilux, fixed 3rd, 4.1 diff")
           )
ax.legend(handles=handles)

#plt.subplot(212)
#plt.plot(stock_hilux.gear_data(), label="Stock Hilux 3.0 D4D, gear")

plt.show()
