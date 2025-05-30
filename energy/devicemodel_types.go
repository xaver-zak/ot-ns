// Copyright (c) 2020-2025, The OTNS Authors.
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
	RxConsumption       float64
	SleepConsumption    float64
	DisabledConsumption float64
	TxPowerConsumption  map[int]float64 // dBm -> kW
}

// TODO make CLI configurable
// TODO expand to radiomodel for radio properties of each device model

// device model registry
// power consumption was measured as whole SoC to better reflect the real conditions
// any new device models added to registry require recompile OTNS ./script/install
var DeviceModels = map[string]*DeviceModel{
	"stm32wb55rg": { 
		Name:                "stm32wb55rg",
		RxConsumption:       0.00001485, //kilowatts @ V = 3.3V i = 4.5 mA
		SleepConsumption:    0.00001485, //kilowatts @ V = 3.3V i = 4.5 mA
		DisabledConsumption: 0.00000011, //kilowatts, to be confirmed
		TxPowerConsumption: map[int]float64{
			0:   0.00001716, 			 //kilowatts @ V = 3.3V i = 5.2 mA
		},
	},
	"xxx": {
		Name:                "xxx",
		RxConsumption:       0.00009000,	// NOT real value w8ing for paper release
		SleepConsumption:    0.00000052, 	// NOT real value w8ing for paper release		// xxaver TODO: Check if this state only occurs when the device is sleeping
		DisabledConsumption: 0.00005000,	// NOT real value w8ing for paper release		// openthread/include/openthread/platform/radio.h:422
		TxPowerConsumption: map[int]float64{
			-20: 0.000030000,				// NOT real value w8ing for paper release
			-10: 0.000050000,				// NOT real value w8ing for paper release
			0:   0.000100000,				// NOT real value w8ing for paper release
			10:  0.000300000,				// NOT real value w8ing for paper release
			20:  0.000500000,				// NOT real value w8ing for paper release
		},
	},
	"yyy": {
		Name:                "yyy",
		RxConsumption:       0.00008481,	// NOT real value w8ing for paper release
		SleepConsumption:    0.00000111,	// NOT real value w8ing for paper release
		DisabledConsumption: 0.00004000,	// NOT real value w8ing for paper release
		TxPowerConsumption: map[int]float64{
			-20: 0.0000010000, 				// NOT real value w8ing for paper release
			-10: 0.0000020000, 				// NOT real value w8ing for paper release
			0:   0.0000030000, 				// NOT real value w8ing for paper release
		},
	},
	
	// Add more models here...
}
