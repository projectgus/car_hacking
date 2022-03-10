#![no_main]
#![no_std]

extern crate panic_itm; // panic handler

use cortex_m::{iprint, iprintln, peripheral::ITM};
use cortex_m_rt::entry;
use heapless::Vec;
#[allow(unused_imports)]
use stm32f3xx_hal::gpio::marker::Gpio;
use stm32f3xx_hal::gpio::PushPull;
use stm32f3xx_hal::gpio::AF7;
use stm32f3xx_hal::gpio::{PD0, PD1};
mod monotimer;
use monotimer::MonoTimer;
use stm32f3xx_hal::can::Can;
use stm32f3xx_hal::pac::usart1;

use bxcan::filter::Mask32;
use bxcan::{Frame, StandardId};

use stm32f3xx_hal::{
    pac::{self, USART1},
    prelude::*,
    serial::Serial,
};

#[entry]
fn main() -> ! {
    let (usart1, _mono_timer, _itm, can) = init();

    defmt::trace!("initialized");

    // A buffer with 32 bytes of capacity
    let mut buffer: Vec<u8, 32> = Vec::new();

    loop {
        buffer.clear();

        loop {
            while usart1.isr.read().rxne().bit_is_clear() {}
            let byte = usart1.rdr.read().rdr().bits() as u8;

            if buffer.push(byte).is_err() {
                defmt::trace!("buffer full");
                // buffer full
                for byte in b"error: buffer full\n\r" {
                    while usart1.isr.read().txe().bit_is_clear() {}
                    usart1.tdr.write(|w| w.tdr().bits(u16::from(*byte)));
                }

                break;
            }

            // Carriage return
            if byte == 13 {
                defmt::trace!("echoing");
                // Respond
                for byte in buffer.iter().rev().chain(&[b'\n', b'\r']) {
                    while usart1.isr.read().txe().bit_is_clear() {}
                    usart1.tdr.write(|w| w.tdr().bits(u16::from(*byte)));
                }

                break;
            }
        }
    }
}

pub type CanTx = PD1<AF7<PushPull>>;
pub type CanRx = PD0<AF7<PushPull>>;
pub type CanInstance = bxcan::Can<stm32f3xx_hal::can::Can<CanTx, CanRx>>;

fn init() -> (
    &'static mut usart1::RegisterBlock,
    MonoTimer,
    ITM,
    CanInstance,
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

    unsafe {
        (
            &mut *(USART1::ptr() as *mut _),
            MonoTimer::new(cp.DWT, clocks),
            cp.ITM,
            can,
        )
    }
}
