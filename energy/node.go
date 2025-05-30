// Copyright (c) 2022-2024, The OTNS Authors.
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

import (
	"sort"
	"github.com/openthread/ot-ns/logger"
	. "github.com/openthread/ot-ns/radiomodel"
	. "github.com/openthread/ot-ns/types"
)

type NodeEnergy struct {
	NodeId  int
	Model   *DeviceModel
	radio   RadioStatus
	txPower *DbValue

	Disabled float64
	Sleep    float64
	Tx       float64
	Rx       float64
}

// increase timeSpent for specific radio mode
func (node *NodeEnergy) ComputeRadioState(timestamp uint64) {
	delta := timestamp - node.radio.Timestamp
	switch node.radio.State {
	case RadioDisabled:
		node.radio.SpentDisabled += delta
	case RadioSleep:
		node.radio.SpentSleep += delta
	case RadioTx:
		node.radio.SpentTx[int(*node.txPower)] += delta // Use map for SpentTx
	case RadioRx:
		node.radio.SpentRx += delta
	case RadioInvalid:
		break // skip bookkeeping in this case
	default:
		logger.Panicf("unknown radio state: %v", node.radio.State)
	}
	node.radio.Timestamp = timestamp
}

func (node *NodeEnergy) SetRadioState(state RadioStates, timestamp uint64) {
	//Mandatory: compute energy consumed by the radio first.
	node.ComputeRadioState(timestamp)
	node.radio.State = state
}

func newNode(nodeID int, timestamp uint64, model *string, txPower *DbValue) *NodeEnergy {
	node := &NodeEnergy{
		NodeId:  nodeID,
		Model:   DeviceModels[*model],
		txPower: txPower,
		radio: RadioStatus{
			State:         RadioDisabled,
			SpentDisabled: 0.0,
			SpentSleep:    0.0,
			SpentRx:       0.0,
			SpentTx:       make(SpentTxMap),
			Timestamp:     timestamp,
		},
	}
	return node
}

// Set device model struct for power consumption if model found in DeviceModels
func (node *NodeEnergy) SetDeviceModel(model string) bool {
	dm, ok := DeviceModels[model]
	if !ok || dm == nil {
		return false // model not found
	}
	node.Model = dm
	return true
}

// Calculate total transmit‐energy used by a node at each power level
// Energy [mJ] = Power [kW] * Time [us]
func (node *NodeEnergy) CalculateTxEnergy() float64 {
	var txEnergy float64
	for txPower, timeSpent := range node.radio.SpentTx {
		consumption, ok := node.Model.TxPowerConsumption[txPower]
		if !ok {
			// Handle unlisted TX power consumption
			consumption = node.FindAndAddTxPowerConsumption(txPower)
		}
		txEnergy += consumption * float64(timeSpent)
	}
	return txEnergy
}

// Function handles missing tx power consumption for specific Tx power of Device Model. 
// It looks for nearest higher defined Tx power if input tx power undefined in device model tx power consumption
// and adds it to tx device model consumption list. If nodes tx power is bigger then known max tx value
// use maximum known tx power consumption.
// Returns and extend the energy consumption used for specific txPower of device model.
func (node *NodeEnergy) FindAndAddTxPowerConsumption(txPower int) float64 {
	// Collect all defined tx power consumptions for specific device model 
	txList := make([]int, 0, len(node.Model.TxPowerConsumption))
	for k := range node.Model.TxPowerConsumption {
		txList = append(txList, k)
	}
	sort.Ints(txList)

	undefinedValue := 0.000100000 // value used when empty tx list or appropriate value not found

	if len(txList) == 0 {
		// Handle empty list of tx power consumptions
		node.Model.SetTxPowerConsumption(txPower, undefinedValue)
		return undefinedValue
	} else if txPower > txList[len(txList)-1] {
		// Handle if nodes tx power is bigger than defined in deviceModel 
		maxVal := node.Model.TxPowerConsumption[txList[len(txList)-1]]
		node.Model.SetTxPowerConsumption(txPower, maxVal)
		return maxVal
	} else {
		for _, k := range txList {
			// Finds the nearest higher defined Tx power in deviceModel 
			if k > txPower {
				firstHigherVal := node.Model.TxPowerConsumption[k]
				node.Model.SetTxPowerConsumption(txPower, firstHigherVal)
				return firstHigherVal
			}
		}
	}
	return undefinedValue
}

func (node *NodeEnergy) CalculateRxEnergy() float64 {
	return node.Model.RxConsumption * float64(node.radio.SpentRx)
}

func (node *NodeEnergy) CalculateDisabledEnergy() float64 {
	return node.Model.DisabledConsumption * float64(node.radio.SpentDisabled)
}

func (node *NodeEnergy) CalculateSleepEnergy() float64 {
	return node.Model.SleepConsumption * float64(node.radio.SpentSleep)
}
