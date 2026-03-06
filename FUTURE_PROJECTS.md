# Future Projects
# Rev: 1.0

## HVAC Energy Profiler (separate integration)

### Concept
A separate HA custom integration that builds energy consumption profiles for HVAC equipment
by correlating BuzzBridge equipment state changes or other near real time hvac status entitires
with whole-home energy sensor readings.

### How It Works
1. User configures: hvac/BuzzBridge equipment entities + whole-home energy sensor entity + $/kWh rate
   a. there may be multiple HVAC systems in a home so the integration has to maintain a profile
      for each hvac system available.  
   b. so, per system we need to look closely at parameters available, first chocie might be climate
      entities because they should have the best near real time on/off status within attributes. Other
      sensor entities might be able to be used, but probably less accurate on state changes (BuzzBridge)
   c. regardless of how many hvac systems there are, there should only be one total home energy use entity
   d. there might be additional energy use entities directly associated with hvac systems. example: I use
      sense to monitor by power. From sense I have both total home energy consumption and I have two branch
      monitors from sense that monitor the outdoor energy use of the compressors. in my case that would provide 
      additional information on two of the three units.
2. Integration watches for equipment state transitions (on→off, off→on) and type: cooling / heating
3. On each transition, captures energy delta during the run window
4. Subtracts baseline energy use (learned from periods when all HVAC is off)
5. Over time, builds a statistical model per equipment type:
   - cool1 average draw: X kW
   - heat1 average draw: Y kW (or therms for gas)
   - fan average draw: Z kW
   - aux heat average draw: W kW
6. Model improves with more data — accounts for outdoor temp, stage, season
7. Produces daily/monthly/yearly cost estimates with confidence intervals

### Calculated Outputs
- Per-equipment kW draw estimate (with confidence)
- Daily/monthly/YTD HVAC energy cost
- Cost per degree day (efficiency metric)
- Seasonal comparistons (this March vs last March)
- Anomaly detection ("your AC is drawing 20% more than last summer")

### Dependencies
- HVAC status entities or BuzzBridge entities (for equipment state entities)
- Whole-home energy monitor (e.g., Emporia Vue, Sense, utility smart meter)
- User-provided electricity rate ($/kWh)
- Optional: gas rate ($/therm) for gas heat systems

### Technical Notes
- Needs weeks of data before estimates are reliable
- Should store learned profiles in HA .storage
- Gas heat is trickier — may need a gas meter entity or manual input
- Multi-stage equipment (cool1 vs cool2) will have different profiles
- Baseline subtraction is key — house loads vary by time of day
- Consider using machine learning (simple linear regression) for outdoor temp correlation

### Status
- Sidelined for after BuzzBridge v1 is complete
