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
	"fmt"
	"os"
	"sort"

	"github.com/openthread/ot-ns/logger"
	. "github.com/openthread/ot-ns/radiomodel"
	. "github.com/openthread/ot-ns/types"
)

type EnergyAnalyser struct {
	nodes                map[int]*NodeEnergy
	networkHistory       []NetworkConsumption
	energyHistoryByNodes [][]*NodeEnergy
	title                string
}

func (e *EnergyAnalyser) AddNode(nodeID int, timestamp uint64, model *string, txPower *DbValue, nodeMode *NodeMode) {
	if _, ok := e.nodes[nodeID]; ok {
		return
	}
	e.nodes[nodeID] = newNode(nodeID, timestamp, model, txPower, nodeMode)
}

func (e *EnergyAnalyser) DeleteNode(nodeID int) {
	delete(e.nodes, nodeID)

	if len(e.nodes) == 0 {
		e.ClearEnergyData()
	}
}

func (e *EnergyAnalyser) GetNode(nodeID int) *NodeEnergy {
	return e.nodes[nodeID]
}

func (e *EnergyAnalyser) GetNetworkEnergyHistory() []NetworkConsumption {
	return e.networkHistory
}

func (e *EnergyAnalyser) GetEnergyHistoryByNodes() [][]*NodeEnergy {
	return e.energyHistoryByNodes
}

func (e *EnergyAnalyser) GetLatestEnergyOfNodes() []*NodeEnergy {
	return e.energyHistoryByNodes[len(e.energyHistoryByNodes)-1]
}

func (e *EnergyAnalyser) GetNetworkLatestSnap() NetworkConsumption {
	// lastSnap:=  e.networkHistory[len(e.networkHistory)-1]
	return e.networkHistory[len(e.networkHistory)-1]
}

func (e *EnergyAnalyser) StoreNetworkEnergy(timestamp uint64) {
	nodesEnergySnapshot := make([]*NodeEnergy, 0, len(e.nodes))
	networkSnapshot := NetworkConsumption{
		Timestamp: timestamp,
	}

	netSize := float64(len(e.nodes))
	for _, node := range e.nodes {
		node.ComputeRadioState(timestamp)

		e := &NodeEnergy{
			NodeId:   node.NodeId,
			Disabled: node.CalculateDisabledEnergy(),
			Sleep:    node.CalculateSleepEnergy(),
			Tx:       node.CalculateTxEnergy(),
			Rx:       node.CalculateRxEnergy(),
		}

		networkSnapshot.EnergyConsDisabled += e.Disabled / netSize
		networkSnapshot.EnergyConsSleep += e.Sleep / netSize
		networkSnapshot.EnergyConsTx += e.Tx / netSize
		networkSnapshot.EnergyConsRx += e.Rx / netSize
		nodesEnergySnapshot = append(nodesEnergySnapshot, e)
	}

	e.networkHistory = append(e.networkHistory, networkSnapshot)
	e.energyHistoryByNodes = append(e.energyHistoryByNodes, nodesEnergySnapshot)
}

func (e *EnergyAnalyser) CreateEnergyResultsDir() {
	dir, _ := os.Getwd()

	if _, err := os.Stat(dir + "/energy_results"); os.IsNotExist(err) {
		err := os.Mkdir(dir+"/energy_results", 0755)
		if err != nil {
			logger.Error("Failed to create energy_results directory")
			return
		}
	}
}

func (e *EnergyAnalyser) SaveEnergyDataToTxtFile(name string, timestamp uint64) {
	if name == "" {
		if e.title == "" {
			name = "energy"
		} else {
			name = e.title
		}
	}

	//Get current directory and add name to the path
	dir, _ := os.Getwd()

	path := fmt.Sprintf("%s/energy_results/%s", dir, name)
	fileNodes, err := os.Create(path + "_nodes.txt")
	if err != nil {
		logger.Errorf("Error creating file: %v", err)
		return
	}
	defer fileNodes.Close()

	fileNetwork, err := os.Create(path + ".txt")
	if err != nil {
		logger.Errorf("Error creating file: %v", err)
		return
	}
	defer fileNetwork.Close()

	//Save all nodes' energy data to file
	e.writeEnergyByNodesTxt(fileNodes, timestamp)

	//Save network energy data to file (timestamp converted to milliseconds)
	e.writeNetworkEnergyTxt(fileNetwork, timestamp)
}

func (e *EnergyAnalyser) SaveEnergyDataToCsvFile(name string, timestamp uint64) {
	if name == "" {
		if e.title == "" {
			name = "energy"
		} else {
			name = e.title
		}
	}

	dir, _ := os.Getwd()

	path := fmt.Sprintf("%s/energy_results/%s", dir, name)
	fileNodes, err := os.Create(path + "_nodes.csv")
	if err != nil {
		logger.Errorf("Error creating file: %v", err)
		return
	}
	defer fileNodes.Close()

	fileNetwork, err := os.Create(path + ".csv")
	if err != nil {
		logger.Errorf("Error creating file: %v", err)
		return
	}
	defer fileNetwork.Close()

	// e.StoreNetworkEnergy(timestamp)
	//Save all nodes' energy data to .CSV file
	e.writeEnergyByNodesCsv(fileNodes)

	//Save network energy data to .CSV file (timestamp converted to milliseconds)
	e.writeNetworkEnergyCsv(fileNetwork)
}

func (e *EnergyAnalyser) writeEnergyByNodesTxt(fileNodes *os.File, timestamp uint64) {
	fmt.Fprintf(fileNodes, "Duration of the simulated network (in milliseconds): %d\n", timestamp/1000)
	fmt.Fprintf(fileNodes, "ID\tDeviceModel\tDisabled (mJ)\tSleep (mJ)\tTransmiting (mJ)\tReceiving (mJ)\n")

	sortedNodes := make([]int, 0, len(e.nodes))
	for id := range e.nodes {
		sortedNodes = append(sortedNodes, id)
	}
	sort.Ints(sortedNodes)

	for _, id := range sortedNodes {
		node := e.nodes[id]
		fmt.Fprintf(fileNodes, "%d\t%s\t%f\t%f\t%f\t%f\n",
			id,
			node.Model.GetName(),
			node.CalculateDisabledEnergy(),
			node.CalculateSleepEnergy(),
			node.CalculateTxEnergy(),
			node.CalculateRxEnergy(),
		)
	}
}

func (e *EnergyAnalyser) writeEnergyByNodesCsv(fileNodes *os.File) {
	fmt.Fprintf(fileNodes, "Node ID,Device Model,Disabled [mJ],Sleep [mJ],Transmiting [mJ],Receiving [mJ],")
	fmt.Fprintf(fileNodes, "Time Disabled [ms],Time Sleep [ms],Time Transmiting [ms],Time Receiving [ms]\n")
	sortedNodes := make([]int, 0, len(e.nodes))
	for id := range e.nodes {
		sortedNodes = append(sortedNodes, id)
	}
	sort.Ints(sortedNodes)

	for _, id := range sortedNodes {
		node := e.nodes[id]
		fmt.Fprintf(fileNodes, "%d,%s,%f,%f,%f,%f,%f,%f,%f,%f\n",
			id,
			node.Model.Name,
			node.CalculateDisabledEnergy(),
			node.CalculateSleepEnergy(),
			node.CalculateTxEnergy(),
			node.CalculateRxEnergy(),
			float64(node.radio.SpentDisabled/1000),
			float64(node.radio.SpentSleep/1000),
			node.GetTotalTxTimeSpent()/1000,
			float64(node.radio.SpentRx/1000),
		)
	}
}

func (e *EnergyAnalyser) writeNetworkEnergyTxt(fileNetwork *os.File, timestamp uint64) {
	fmt.Fprintf(fileNetwork, "Duration of the simulated network (in milliseconds): %d\n", timestamp/1000)
	fmt.Fprintf(fileNetwork, "Time (ms)\tDisabled (mJ)\tSleep (mJ)\tTransmiting (mJ)\tReceiving (mJ)\n")
	for _, snapshot := range e.networkHistory {
		fmt.Fprintf(fileNetwork, "%d\t%f\t%f\t%f\t%f\n",
			snapshot.Timestamp/1000,
			snapshot.EnergyConsDisabled,
			snapshot.EnergyConsSleep,
			snapshot.EnergyConsTx,
			snapshot.EnergyConsRx,
		)
	}
}

func (e *EnergyAnalyser) writeNetworkEnergyCsv(fileNetwork *os.File) {
	fmt.Fprintf(fileNetwork, "Time [ms],Disabled [mJ],Sleep [mJ],Transmiting [mJ],Receiving [mJ]\n")
	for _, snapshot := range e.networkHistory {
		fmt.Fprintf(fileNetwork, "%d,%f,%f,%f,%f\n",
			snapshot.Timestamp/1000,
			snapshot.EnergyConsDisabled,
			snapshot.EnergyConsSleep,
			snapshot.EnergyConsTx,
			snapshot.EnergyConsRx,
		)
	}
}

func (e *EnergyAnalyser) ClearEnergyData() {
	logger.Debugf("Node's energy data cleared")
	e.networkHistory = make([]NetworkConsumption, 0, 3600)
	e.energyHistoryByNodes = make([][]*NodeEnergy, 0, 3600)
}

func (e *EnergyAnalyser) SetTitle(title string) {
	e.title = title
}

func (e *EnergyAnalyser) GetAllDeviceModelsBrief() []string {
	out := make([]string, 0, len(DeviceModels))
	for key, dm := range DeviceModels {
		devModelInfo := fmt.Sprintf("%s\t %s, %s", key, dm.Name, dm.Description)
		out = append(out, devModelInfo)
	}
	sort.Strings(out)
	return out
}

// Set device model struct for specific node
func (e *EnergyAnalyser) SetDeviceModel(nodeID int, model string) bool {
	if _, ok := e.nodes[nodeID]; ok {
		return false
	}
	if e.nodes[nodeID].SetDeviceModel(model) {
		return true
	} else {
		return false
	}
}

func (e *EnergyAnalyser) DeviceModelExists(model string) bool {
	_, exists := DeviceModels[model]
	return exists
}

func NewEnergyAnalyser() *EnergyAnalyser {
	ea := &EnergyAnalyser{
		nodes:                make(map[int]*NodeEnergy),
		networkHistory:       make([]NetworkConsumption, 0, 3600), //Start with space for 1 sample every 30s for 1 hour = 1*60*60/30 = 3600 samples
		energyHistoryByNodes: make([][]*NodeEnergy, 0, 3600),
	}
	return ea
}
