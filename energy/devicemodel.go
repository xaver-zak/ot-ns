// Copyright (c) 2020-2026, The OTNS Authors.
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
// 1. Redistributions of source code must retain the above copyright
//    notice, this list of conditions and the following disclaimer.
// 2. Redistributions in binary form must reproduce the above copyright
//    notice, this list of conditions and the following disclaimer in the
//    documentation and/or other materials provided with the distribution.
// 3. Neither the name of the copyright holder nor the
//    names of its contributors may be used to endorse or promote products
//    derived from this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.

package energy

// Get device model Name
func (dm *DeviceModel) GetName() string {
	return dm.Name
}

// Set device model Name
func (dm *DeviceModel) SetName(name string) {
	dm.Name = name
}

// Get power consumption of device when radio in Sleep mode
func (dm *DeviceModel) GetSleepConsumption() float64 {
	return dm.SleepConsumption
}

// Set power consumption of device in radio Sleep mode
func (dm *DeviceModel) SetSleepConsumption(consumption float64) {
	dm.SleepConsumption = consumption
}

// Get power consumption of device in radio Disabled
func (dm *DeviceModel) GetDisabledConsumption() float64 {
	return dm.DisabledConsumption
}

// Set power consumption of device in when radio Disabled
func (dm *DeviceModel) SetDisabledConsumption(consumption float64) {
	dm.DisabledConsumption = consumption
}

// Get power consumption of device when radio Transmitting at specific Tx Power
func (dm *DeviceModel) GetTxPowerConsumption(txPower int) float64 {
	return dm.TxPowerConsumption[txPower]
}

// Set power consumption of device when radio Transmitting at specific Tx Power
func (dm *DeviceModel) SetTxPowerConsumption(txPower int, consumption float64) {
	if dm.TxPowerConsumption == nil {
		dm.TxPowerConsumption = make(map[int]float64)
	}
	dm.TxPowerConsumption[txPower] = consumption
}
