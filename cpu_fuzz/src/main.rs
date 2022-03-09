#![no_main]
#![no_std]

extern crate panic_itm; // panic handler

#[allow(unused_imports)]
use cortex_m::{iprint, iprintln, peripheral::ITM};
use cortex_m_rt::entry;
use heapless::Vec;
mod monotimer;
use monotimer::MonoTimer;
use stm32f3_discovery::stm32f3xx_hal::pac::usart1;

mod can;
use can::CANBus;
use stm32f3_discovery::stm32f3xx_hal::{
    pac::{self, USART1},
    prelude::*,
    serial::Serial,
};

#[entry]
fn main() -> ! {
    let (usart1, _mono_timer, _itm) = init();

    // A buffer with 32 bytes of capacity
    let mut buffer: Vec<u8, 32> = Vec::new();

    loop {
        buffer.clear();

        loop {
            while usart1.isr.read().rxne().bit_is_clear() {}
            let byte = usart1.rdr.read().rdr().bits() as u8;

            if buffer.push(byte).is_err() {
                // buffer full
                for byte in b"error: buffer full\n\r" {
                    while usart1.isr.read().txe().bit_is_clear() {}
                    usart1.tdr.write(|w| w.tdr().bits(u16::from(*byte)));
                }

                break;
            }

            // Carriage return
            if byte == 13 {
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

fn init() -> (&'static mut usart1::RegisterBlock, MonoTimer, ITM) {
    let cp = cortex_m::Peripherals::take().unwrap();
    let dp = pac::Peripherals::take().unwrap();

    let mut flash = dp.FLASH.constrain();
    let mut rcc = dp.RCC.constrain();

    let clocks = rcc.cfgr.freeze(&mut flash.acr);

    let mut gpiob = dp.GPIOB.split(&mut rcc.ahb);
    let mut gpioc = dp.GPIOC.split(&mut rcc.ahb);

    let tx = gpioc
        .pc4
        .into_af7_push_pull(&mut gpioc.moder, &mut gpioc.otyper, &mut gpioc.afrl);
    let rx = gpioc
        .pc5
        .into_af7_push_pull(&mut gpioc.moder, &mut gpioc.otyper, &mut gpioc.afrl);

    Serial::new(dp.USART1, (tx, rx), 115_200.Bd(), clocks, &mut rcc.apb2);

    let (can_rx, can_tx) = cortex_m::interrupt::free(|cs| {
        (
            gpiob.pb8.into_alternate_af4(cs),
            gpiob.pb9.into_alternate_af4(cs),
        )
    });

    let can = CANBus::new(device.CAN, can_rx, can_tx);
    can.listen(can::Event::RxMessagePending);

    unsafe {
        (
            &mut *(USART1::ptr() as *mut _),
            MonoTimer::new(cp.DWT, clocks),
            cp.ITM,
        )
    }
}
