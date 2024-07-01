#!/usr/bin/env python
import math
import matplotlib.pyplot as plt


class Motor:
    def torque(self, rpm):
        """ Returns motor torque in Nm at a given rpm. """
        raise NotImplementedError

    def power(self, rpm):
        """ Returns motor power in kW for a given rpm. """
        return self.torque(rpm) * math.pi * rpm / 30 / 1000


class EVMotor(Motor):
    def __init__(self, max_power, max_torque, max_power_rpm, max_rpm):
        self.max_power = max_power
        self.max_torque = max_torque
        self.max_power_rpm = max_power_rpm
        self.max_rpm = max_rpm

    def torque(self, rpm):
        # Assume an "ideal" AC motor, constant torque up to a max power point
        # then torque linearly degrades to the max RPM point which has 0 torque.
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


class ICEEngine(Motor):
    def __init__(self):
        pass

    def torque(self, rpm):
        min_rpm, min_torque = self._T[0]
        if rpm < min_rpm:
            # "slip" the clutch when starting from below idle rpm...
            return max(.1, rpm / min_rpm) * min_torque

        # Otherwise interpolate between two torque points
        for (a_r, a_t), (b_r, b_t) in zip(self._T, self._T[1:]):
            if a_r <= rpm <= b_r:
                r = (rpm - a_r) / (b_r - a_r)
                return (r * b_t) + ((1 - r) * a_t)

        # Above redline?
        return 0


class D4D1KD(ICEEngine):
    # rpm to torque, according to
    # https://www.4x4community.co.za/forum/showthread.php/10949-2-5-D4D-vs-3-0-D4D
    _T = [
        (1000, 310),
        (1200, 343),
        (3300, 343),
        (3500, 325),
        (5000, 90),
    ]


class I43RZFE(ICEEngine):
    # rpm to torque, according to
    # https://www.advrider.com/f/threads/a-toyota-based-adventure-rig-brainstorming.831138/page-2
    _T = [
        (1000, 175),
        (1800, 205),
        (2000, 220),
        (4000, 230),
        (4500, 220),
        (5200, 195),
        ]


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
        gear = self.select_gear(kph)
        motor_rpm = self.get_motor_rpm(kph)
        return self.engine.torque(motor_rpm) * self.gears[gear] * self.final_drive

    def get_motor_rpm(self, kph):
        wheel_rpm = self.wheel.wheel_rpm(kph)
        driveshaft_rpm = wheel_rpm * self.final_drive
        gear = self.select_gear(kph)
        return driveshaft_rpm * self.gears[gear]

    def torque_data(self):
        # making use of implicit x axis of len(ys)
        return [self.wheel_torque(kph) for kph in range(0, 121)]

    def gear_data(self):
        # making use of implicit x axis of len(ys)
        return [self.select_gear(kph) for kph in range(0, 121)]

    def motor_rpm_data(self):
        # making use of implicit x axis of len(ys)
        return [self.get_motor_rpm(kph) for kph in range(0, 121)]


stock_wheels = Wheel(205, 70, 15)
stock_td_hilux = Vehicle(
    D4D1KD(), stock_wheels, [4.313, 2.330, 1.436, 1.000, 0.838], 3.583
)


# This car doesn't exist as this series Hilux as the 2TR-FE engine,
# but I couldn't find a power curve for that one. The 3RZ-FE is the predecessor
# with similar overall specs but maybe no variable valve timing.
stock_i4_hilux = Vehicle(
    I43RZFE(), stock_wheels, [3.830, 2.062, 1.436, 1.000, 0.838], 4.1)

kona_wheels = Wheel(215, 55, 17)
kona = Vehicle(KonaMotor(), kona_wheels, [1.0], 7.981)

conv_hilux_3rd = Vehicle(KonaMotor(), stock_wheels, [1.436], 3.583)
conv_hilux_2nd = Vehicle(KonaMotor(), stock_wheels, [2.330], 3.583)
#conv_hilux_petrol_2nd = Vehicle(KonaMotor(), stock_wheels, [2.062], 3.583)  # diesel diff

conv_hilux_3rd_41diff = Vehicle(KonaMotor(), stock_wheels, [1.436], 4.1)

fig, (ax1, ax2) = plt.subplots(2, 1)

handles = (ax1.plot(kona.torque_data(), label="Kona Electric") +
           ax1.plot(stock_td_hilux.torque_data(), label="Stock Hilux 3.0 D4D, 5sp manual") +
           ax1.plot(stock_i4_hilux.torque_data(), label="Stock-ish Hilux 2.7, 5sp manual") +
           ax1.plot(conv_hilux_2nd.torque_data(), label="Electric Hilux, locked in 2nd (diesel gearbox)") +
           #ax1.plot(conv_hilux_petrol_2nd.torque_data(), label="Electric Hilux, fixed petrol 2nd (diesel diff)") +
           ax1.plot(conv_hilux_3rd.torque_data(), label="Electric Hilux, locked in 3rd") +
           ax1.plot(conv_hilux_3rd_41diff.torque_data(), label="Electric Hilux, locked in 3rd, 4.1 diff")
           )
ax1.set_xlabel("Speed (km/h)")
ax1.set_ylabel("Wheel Torque (Nm)")
ax1.legend(handles=handles)

ax2.set_xlabel("Speed (km/h)")
ax2.set_ylabel("Motor RPM")
dashes = [1, 2]
handles = (ax2.plot(kona.motor_rpm_data(), dashes=dashes) +
           ax2.plot(stock_td_hilux.motor_rpm_data(), dashes=dashes) +
           ax2.plot(stock_i4_hilux.motor_rpm_data(), dashes=dashes) +
           ax2.plot(conv_hilux_2nd.motor_rpm_data(), dashes=dashes) +
           #ax2.plot(conv_hilux_petrol_2nd.motor_rpm_data(), dashes=dashes) +
           ax2.plot(conv_hilux_3rd.motor_rpm_data(), dashes=dashes) +
           ax2.plot(conv_hilux_3rd_41diff.motor_rpm_data(), dashes=dashes)
           )

ax1.grid(True, linestyle=':')
ax2.grid(True, linestyle=':')

fig.tight_layout()
plt.show()
