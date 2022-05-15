#![no_main]
#![no_std]

use embedded_time::duration::Milliseconds;
use no_std_compat::str;

use defmt_rtt as _;
use panic_probe as _; // global logger

use cortex_m::peripheral::ITM;
use cortex_m_rt::entry;
use heapless::Vec;

mod monotimer;
use bxcan::filter::Mask32;
use bxcan::{Frame, Id, StandardId};
use embedded_time::Clock;
use monotimer::MonoTimer;
use stm32f3xx_hal::can;
use stm32f3xx_hal::gpio;
use stm32f3xx_hal::pac;
use stm32f3xx_hal::pac::usart1;
use stm32f3xx_hal::prelude::*;
use stm32f3xx_hal::serial;

const fn const_standard_id(id: u16) -> Id {
    match StandardId::new(id) {
        Some(new_id) => Id::Standard(new_id),
        None => panic!("Bad Standard Id value"),
    }
}

const HEARTBEAT_ID: Id = const_standard_id(0x55e); // About every ~400ms
                                                   //const HEARTBEAT_ALT_ID: Id = const_standard_id(0x65e); // Occasional
const STATUS_ID: Id = const_standard_id(0x197); // Very frequent

#[entry]
fn main() -> ! {
    let (usart1, timer, _itm, mut can, mut trigger) = init();

    defmt::trace!("initialised, waiting for test ID");

    let mut buffer: Vec<u8, 8> = Vec::new();

    loop {
        trigger.set_low().ok();

        if let Some(id) = try_read_id(usart1, &mut buffer) {
            if let Some(can_id) = StandardId::new(id) {
                let can_data: [u8; 8] = [0xFF; 8];
                let can_frame = Frame::new_data(can_id, can_data);

                // Wait until gear lever has sent a heartbeat and then a status, and then immediately send our message
                // (this is to try and make sure the status of the selector CPU is consistent each time)
                wait_for_can_frame(HEARTBEAT_ID, &mut can, &timer, Milliseconds::new(1000))
                    .unwrap();
                wait_for_can_frame(STATUS_ID, &mut can, &timer, Milliseconds::new(250)).unwrap();

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

fn wait_for_can_frame(
    id: bxcan::Id,
    can: &mut CanInstance,
    timer: &MainTimer,
    timeout: Milliseconds,
) -> Option<Frame> {
    let deadline = timer.new_timer(timeout).start().unwrap();

    // Note: this timeout currently doesn't work
    while !deadline.is_expired().unwrap() {
        if let Ok(rx_frame) = can.receive() {
            if rx_frame.id() == id {
                return Some(rx_frame);
            }
        }
    }
    None
}

fn try_read_id(usart1: &mut usart1::RegisterBlock, buffer: &mut Vec<u8, 8>) -> Option<u16> {
    loop {
        if usart1.isr.read().rxne().bit_is_clear() {
            return None;
        }
        let byte = usart1.rdr.read().rdr().bits() as u8;

        if (b'0' <= byte && byte <= b'9')
            || (b'a' <= byte && byte <= b'f')
            || (b'A' <= byte && byte <= b'F')
        {
            if buffer.push(byte).is_err() {
                defmt::error!("rx buffer full");
                buffer.clear();
                return None;
            }
        }

        if byte == b'\n' {
            if let Ok(s) = str::from_utf8(&buffer) {
                defmt::trace!("buffer {}", s);
                if let Ok(n) = u16::from_str_radix(s, 16) {
                    defmt::info!("read ID {:#x}", n);
                    buffer.clear();
                    return Some(n);
                } else {
                    defmt::error!("failed to parse hex");
                }
            } else {
                defmt::error!("failed to parse utf8");
            }
            buffer.clear();
            return None;
        }
    }
}

pub type CanTx = gpio::PD1<gpio::AF7<gpio::PushPull>>;
pub type CanRx = gpio::PD0<gpio::AF7<gpio::PushPull>>;
pub type CanInstance = bxcan::Can<can::Can<CanTx, CanRx>>;

pub type TriggerOutput = gpio::PC12<gpio::Output<gpio::PushPull>>;

const HCLK_FREQ: u32 = 64_000_000;
pub type MainTimer = MonoTimer<HCLK_FREQ>;

fn init() -> (
    &'static mut usart1::RegisterBlock,
    MainTimer,
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
        .hclk(HCLK_FREQ.Hz().into())
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

    serial::Serial::new(
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
    let mut can = bxcan::Can::builder(can::Can::new(dp.CAN, can_tx, can_rx, &mut rcc.apb1))
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
            &mut *(pac::USART1::ptr() as *mut _),
            MainTimer::new(cp.DWT, clocks),
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
