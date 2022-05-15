use stm32f3xx_hal as hal;

use cortex_m::peripheral::DWT;
use embedded_time::clock::{Clock, Error};
use embedded_time::rate::{Fraction, Hertz};
use embedded_time::Instant;
use hal::rcc::Clocks;

// FREQ_HZ Should be the HCLK frequency (unchecked atm)
#[derive(Clone, Copy)]
pub struct MonoTimer<const FREQ_HZ: u32> {}

impl<const FREQ_HZ: u32> Clock for MonoTimer<FREQ_HZ> {
    type T = u32;
    const SCALING_FACTOR: Fraction = Fraction::new(1, FREQ_HZ);

    fn try_now(&self) -> Result<Instant<Self>, Error> {
        Ok(Instant::new(DWT::cycle_count()))
    }
}

// TODO: What about a refactoring to implement Clock from embedded-time?
impl<const FREQ_HZ: u32> MonoTimer<FREQ_HZ> {
    /// Creates a new `Monotonic` timer
    pub fn new(mut dwt: DWT, clocks: Clocks) -> Self {
        dwt.enable_cycle_counter();

        // now the CYCCNT counter can't be stopped or resetted
        drop(dwt);

        assert!(clocks.hclk() == Hertz(FREQ_HZ));

        MonoTimer {}
    }
}
