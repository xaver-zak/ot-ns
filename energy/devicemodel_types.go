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

type DeviceModel struct {
	Name                string
	Description         string
	RxConsumption       float64
	SleepConsumption    float64
	DisabledConsumption float64
	TxPowerConsumption  map[int]float64 // dBm -> kW
}

// TODO expand to radiomodel for radio properties of each device model
// TODO rework with .json load to mitigate recompile

// device model registry
// power consumption measured as whole SoC.
// Any new device models added to registry require recompile OTNS ./script/install
var DeviceModels = map[string]*DeviceModel{
	"stm32wb55rg": {
		Name:                "STM32WB55RG",
		Description:         "U=3.3V-all data from datasheet",
		RxConsumption:       0.00001485, //kilowatts @ V = 3.3V i = 4.5 mA
		SleepConsumption:    0.00001485, //kilowatts @ V = 3.3V i = 4.5 mA
		DisabledConsumption: 0.00000011, //kilowatts, to bte confirmed
		TxPowerConsumption: map[int]float64{
			0: 0.00001716, //kilowatts @ V = 3.3V i = 5.2 mA
		},
	},
	"esp32h2": { // measured @ U = 3.3V
		Name:                "ESP32-H2",
		Description:         "measured at U=3.3V",
		RxConsumption:       0.0000858186, // radio at Rx idle
		SleepConsumption:    0.0000000825, // radio sleep + device/cpu sleep   // from datasheet
		DisabledConsumption: 0.0000521284, // radio disabled (ifconfig down) cpu idle
		TxPowerConsumption: map[int]float64{ // radio transmitting at different tx power
			-24: 0.0000779209,
			-23: 0.0000779126,
			-22: 0.0000779142,
			-21: 0.0000779166,
			-20: 0.0000779045,
			-19: 0.0000778923,
			-18: 0.0000793767,
			-17: 0.0000793699,
			-16: 0.0000793677,
			-15: 0.0000819075,
			-14: 0.0000818989,
			-13: 0.0000818897,
			-12: 0.0000847587,
			-11: 0.0000847510,
			-10: 0.0000847618,
			-9:  0.0000887625,
			-8:  0.0000887683,
			-7:  0.0000887678,
			-6:  0.0000937528,
			-5:  0.0000937440,
			-4:  0.0000937266,
			-3:  0.0001007521,
			-2:  0.0001007577,
			-1:  0.0001007453,
			0:   0.0001089868,
			1:   0.0001089650,
			2:   0.0001089636,
			3:   0.0001167043,
			4:   0.0001167026,
			5:   0.0001166783,
			6:   0.0001322550,
			7:   0.0001322529,
			8:   0.0001322555,
			9:   0.0001520741,
			10:  0.0001520425,
			11:  0.0001519924,
			12:  0.0001778838,
			13:  0.0001778709,
			14:  0.0001779033,
			15:  0.0002113616,
			16:  0.0002112867,
			17:  0.0002113827,
			18:  0.0002472579,
			19:  0.0002472804,
			20:  0.0002802476,
		},
	},
	"nrf52840": { // measured @ U = 3.0V
		Name:                "nRF52840",
		Description:         "measured at U=3.0V",
		RxConsumption:       0.0000202952, // radio at Rx idle
		SleepConsumption:    0.0000000083, // radio sleep   //src https://docs.nordicsemi.com/bundle/ncs-2.9.0/page/nrf/protocols/thread/overview/power_consumption.html
		DisabledConsumption: 0.0000016787, // radio disabled (ifconfig down) cpu idle
		TxPowerConsumption: map[int]float64{
			-20: 0.0000141036,
			-19: 0.0000141137,
			-18: 0.0000141135,
			-17: 0.0000141163,
			-16: 0.0000145658,
			-15: 0.0000145686,
			-14: 0.0000145676,
			-13: 0.0000145658,
			-12: 0.0000152260,
			-11: 0.0000152161,
			-10: 0.0000151981,
			-9:  0.0000152107,
			-8:  0.0000161509,
			-7:  0.0000161467,
			-6:  0.0000161559,
			-5:  0.0000161528,
			-4:  0.0000173669,
			-3:  0.0000173836,
			-2:  0.0000173844,
			-1:  0.0000173743,
			0:   0.0000202886,
			1:   0.0000203143,
			2:   0.0000292763,
			3:   0.0000317403,
			4:   0.0000337384,
			5:   0.0000355342,
			6:   0.0000391955,
			7:   0.0000413568,
			8:   0.0000455021,
		},
	},
	"nrf5340": { // measured @ U = 3.0V
		Name:          "nRF5340",
		Description:   "measured at U=3.0V",
		RxConsumption: 0.0000156184, // radio at Rx idle
		// RxConsumptionLow:    0.0000134443, 	// TODO special case for nRF5340 when Tx power < 1dBm Rx idle is lower
		SleepConsumption:    0.00000001236, // radio sleep   //src https://docs.nordicsemi.com/bundle/ncs-2.9.0/page/nrf/protocols/thread/overview/power_consumption.html
		DisabledConsumption: 0.0000022175,  // radio disabled (ifconfig down) cpu idle
		TxPowerConsumption: map[int]float64{
			-40: 0.0000099324,
			-39: 0.0000099483,
			-38: 0.0000099415,
			-37: 0.0000099394,
			-36: 0.0000099447,
			-35: 0.0000099406,
			-34: 0.0000099394,
			-33: 0.0000099493,
			-32: 0.0000099416,
			-31: 0.0000099446,
			-30: 0.0000099203,
			-29: 0.0000099385,
			-28: 0.0000099303,
			-27: 0.0000099504,
			-26: 0.0000099398,
			-25: 0.0000099285,
			-24: 0.0000099402,
			-23: 0.0000099423,
			-22: 0.0000099380,
			-21: 0.0000099421,
			-20: 0.0000103551,
			-19: 0.0000103243,
			-18: 0.0000103230,
			-17: 0.0000103303,
			-16: 0.0000105452,
			-15: 0.0000105364,
			-14: 0.0000105203,
			-13: 0.0000105354,
			-12: 0.0000110474,
			-11: 0.0000110528,
			-10: 0.0000110558,
			-9:  0.0000110588,
			-8:  0.0000118000,
			-7:  0.0000120808,
			-6:  0.0000125002,
			-5:  0.0000126586,
			-4:  0.0000130901,
			-3:  0.0000135615,
			-2:  0.0000141279,
			-1:  0.0000142429,
			0:   0.0000150293,
			1:   0.0000178229,
			2:   0.0000180059,
			3:   0.0000190281,
		},
	},

	// Add more models here and run ./script/install...
}
