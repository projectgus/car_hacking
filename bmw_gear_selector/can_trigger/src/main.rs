#![no_main]
#![no_std]

use no_std_compat::str;
use stm32f3xx_hal::gpio::PC12;

use defmt_rtt as _;
use panic_probe as _; // global logger

use cortex_m::peripheral::ITM;
use cortex_m_rt::entry;
use heapless::Vec;
#[allow(unused_imports)]
use stm32f3xx_hal::gpio::marker::Gpio;
use stm32f3xx_hal::gpio::PushPull;
use stm32f3xx_hal::gpio::AF7;
use stm32f3xx_hal::gpio::{PD0, PD1};
mod monotimer;
use bxcan::filter::Mask32;
use bxcan::{Frame, StandardId};
use monotimer::MonoTimer;
use stm32f3xx_hal::can::Can;
use stm32f3xx_hal::pac::usart1;
use stm32f3xx_hal::{
    pac::{self, USART1},
    prelude::*,
    serial::Serial,
};

#[entry]
fn main() -> ! {
    let (usart1, _mono_timer, _itm, mut can, mut trigger) = init();

    defmt::trace!("initialised, waiting for test ID");

    loop {
        trigger.set_low().ok();

        if let Some(id) = read_id(usart1) {
            if let Some(can_id) = StandardId::new(id) {
                let can_data: [u8; 8] = [1; 8];
                let can_frame = Frame::new_data(can_id, can_data);

                // Note: this retries until something ACKs the frame
                can.transmit(&can_frame).expect("Cannot send CAN frame");
                trigger.set_high().ok();
                defmt::trace!("sent CAN frame");
            } else {
                defmt::error!("bad CAN ID {}", id);
            }
        }
    }
}

fn read_id(usart1: &mut usart1::RegisterBlock) -> Option<u16> {
    let mut buffer: Vec<u8, 8> = Vec::new();

    loop {
        while usart1.isr.read().rxne().bit_is_clear() {}
        let byte = usart1.rdr.read().rdr().bits() as u8;

        if (b'0' <= byte && byte <= b'9')
            || (b'a' <= byte && byte <= b'f')
            || (b'A' <= byte && byte <= b'F')
        {
            if buffer.push(byte).is_err() {
                defmt::error!("rx buffer full");
                return None;
            }
        }

        if byte == b'\n' {
            if let Ok(s) = str::from_utf8(&buffer) {
                defmt::trace!("buffer {}", s);
                if let Ok(n) = u16::from_str_radix(s, 16) {
                    defmt::info!("read ID {:x}", n);
                    return Some(n);
                } else {
                    defmt::error!("failed to parse hex");
                    return None;
                }
            } else {
                defmt::error!("failed to parse utf8");
                return None;
            }
        }
    }
}

pub type CanTx = PD1<AF7<PushPull>>;
pub type CanRx = PD0<AF7<PushPull>>;
pub type CanInstance = bxcan::Can<stm32f3xx_hal::can::Can<CanTx, CanRx>>;

pub type TriggerOutput = PC12<stm32f3xx_hal::gpio::Output<stm32f3xx_hal::gpio::PushPull>>;

fn init() -> (
    &'static mut usart1::RegisterBlock,
    MonoTimer,
    ITM,
    CanInstance,
    TriggerOutput,
) {
    let cp = cortex_m::Peripherals::take().unwrap();
    let dp = pac::Peripherals::take().unwrap();

    let mut flash = dp.FLASH.constrain();
    let mut rcc = dp.RCC.constrain();

    let clocks = rcc
        .cfgr
        .use_hse(8.MHz())
        .use_pll()
        .hclk(64.MHz())
        .sysclk(64.MHz())
        .pclk1(32.MHz())
        .pclk2(64.MHz())
        .freeze(&mut flash.acr);

    let mut gpioc = dp.GPIOC.split(&mut rcc.ahb);
    let mut gpiod = dp.GPIOD.split(&mut rcc.ahb);

    let uart_tx = gpioc
        .pc4
        .into_af_push_pull(&mut gpioc.moder, &mut gpioc.otyper, &mut gpioc.afrl);
    let uart_rx = gpioc
        .pc5
        .into_af_push_pull(&mut gpioc.moder, &mut gpioc.otyper, &mut gpioc.afrl);

    Serial::new(
        dp.USART1,
        (uart_tx, uart_rx),
        115_200.Bd(),
        clocks,
        &mut rcc.apb2,
    );

    // Configure CAN RX and TX pins
    let can_rx = gpiod
        .pd0
        .into_af_push_pull(&mut gpiod.moder, &mut gpiod.otyper, &mut gpiod.afrl);

    let can_tx = gpiod
        .pd1
        .into_af_push_pull(&mut gpiod.moder, &mut gpiod.otyper, &mut gpiod.afrl);

    // Initialize the CAN peripheral
    // APB1 (PCLK1): 64MHz, Bit rate: 500kBit/s, Sample Point 87.5%
    // Value was calculated with http://www.bittiming.can-wiki.info/
    let mut can = bxcan::Can::builder(Can::new(dp.CAN, can_tx, can_rx, &mut rcc.apb1))
        .set_bit_timing(0x001c_0003)
        .set_loopback(false)
        .set_silent(false)
        .leave_disabled();

    let mut filters = can.modify_filters();

    filters.enable_bank(0, Mask32::accept_all());

    // Enable filters.
    drop(filters);

    // Sync to the bus and start normal operation.
    can.enable_non_blocking().ok();

    let trigger = gpioc
        .pc12
        .into_push_pull_output(&mut gpioc.moder, &mut gpioc.otyper);

    unsafe {
        (
            &mut *(USART1::ptr() as *mut _),
            MonoTimer::new(cp.DWT, clocks),
            cp.ITM,
            can,
            trigger,
        )
    }
}

// same panicking *behavior* as `panic-probe` but doesn't print a panic message
// this prevents the panic message being printed *twice* when `defmt::panic` is invoked
#[defmt::panic_handler]
fn panic() -> ! {
    cortex_m::asm::udf()
}
