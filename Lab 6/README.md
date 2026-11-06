# Distributed Interaction

**NAMES OF COLLABORATORS HERE**  Wenqing Pan(wp273 ); Mandy Mao(mm3599)；Sirapop Umnakkittikul(su97); Feiyu Zhou(fz283)



---

## Part A: MQTT Messaging


**💡 Brainstorm 5 ideas for messaging between devices**

### Idea 1: Collaborative Maze Game

We want to create a multiplayer maze game where three players work together to control a single character and navigate through obstacles to reach the destination.

Each player uses a Raspberry Pi with an APDS-9960 sensor to control a different aspect of the character's movement:

- **Player 1 – Forward/Backward:** Uses hand gestures to control the character's forward and backward movement.
- **Player 2 – Left/Right:** Uses hand gestures to control the character's left and right movement.
- **Player 3 – Speed:** Uses the distance between their hand and the sensor to control the character's speed. Moving the hand closer speeds up the character, while moving it farther away slows it down.

The three Raspberry Pis send their sensor data through MQTT, and the game combines these inputs to control the character in real time.

Players must communicate and coordinate their movements to avoid obstacles and successfully complete the maze. This game explores how people collaborate when control of a single character is distributed across multiple users.

### Idea 2: Collaborative Color Mixing

We want to create an interactive color-mixing system where three players work together to create a new color using their Raspberry Pis and APDS-9960 sensors.

Each player places a colored object near their sensor, and the sensor detects its RGB values. The three Raspberry Pis send their color data through MQTT to a shared screen.

The screen displays the three players' individual colors and a fourth color created by mixing all three colors together.

As players change the colors in front of their sensors, the mixed color updates in real time.

This interaction allows players to experiment with different color combinations and explore how individual inputs can contribute to a shared visual result.

### Idea 3: Collaborative Virtual Pet

We want to create a virtual pet that three players can take care of together using their Raspberry Pis and sensors.

Each player is responsible for a different activity:

- **Player 1 – Feeding:** Uses different colors to select food for the pet.
- **Player 2 – Playing:** Uses hand gestures to play with the pet.
- **Player 3 – Resting:** Uses the proximity sensor to help the pet sleep or wake up.

The three Raspberry Pis send their sensor data through MQTT, and a shared screen displays the pet's current status, including its hunger, happiness, and energy levels.

Players must communicate and work together to keep the pet healthy and happy. This interaction explores how multiple users can share responsibility for a single virtual character.

### Idea 4: Digital Campfire

We want to create a virtual campfire that responds to the presence and participation of three people.

Each Raspberry Pi uses its proximity sensor to detect whether a player's hand is near the sensor. The devices send their proximity values through MQTT to a shared display.

The campfire changes based on how many players are participating:

- **One player:** A small flame appears.
- **Two players:** The fire becomes brighter and larger.
- **Three players:** The campfire reaches its maximum size.
- **No players:** The fire gradually fades away.

This interaction explores how physical presence can be represented digitally and how multiple people can contribute to a shared experience, even when they are in different locations.

### Idea 5: Collaborative Cooking Game

We want to create a cooking game where three players work together to prepare a virtual meal using their Raspberry Pis and sensors.

Each player controls a different part of the cooking process:

- **Player 1 – Ingredients:** Uses the color sensor to select different ingredients.
- **Player 2 – Cooking Actions:** Uses hand gestures to perform actions such as chopping or stirring.
- **Player 3 – Temperature:** Uses the proximity sensor to control the cooking temperature.

The three Raspberry Pis send their sensor inputs through MQTT, and the shared screen shows the cooking process in real time.

Players must coordinate their actions to follow recipes, control the cooking process, and complete dishes successfully. This game explores communication, teamwork, and coordination when different parts of a task are controlled by different people.

---

## Part B: Collaborative Pixel Grid


**📸 Include: Screenshot of grid + photo of your Pi setup**

### Pixel Grid Screenshot

![Collaborative Pixel Grid](/pixel_grid.png)

### Raspberry Pi Setup

![Raspberry Pi with APDS-9960 Sensor](/pi_setup.jpg)

---

## Part C: Make Your Own

**Requirements:**
- 3+ people, 3+ Pis
- Each Pi contributes sensor input via MQTT
- Meaningful or fun interaction

**Ideas:**

**Sensor Fortune Teller**
- Each Pi sends 0-255 from different sensor
- Server generates fortunes from combined values

**Frankenstories**
- Sensor events → story elements (not text!)
- Red = danger, gesture up = climbed, distance <10cm = suddenly

**Distributed Instrument**
- Each Pi = one musical parameter
- Only works together

**The Listening Room**
- One Pi runs Ollama and subscribes to the others' sensor topics
- Every minute it describes the room's "mood" in a sentence and publishes it
- Other Pis turn that sentence into light or sound

**Others:** Games, presence display, mood ring

### Deliverables

Replace this README with your documentation:

**1. Project Description**
- What does it do? Why interesting? User experience?

**2. Architecture Diagram**
- Hardware, connections, data flow
- Label input/computation/output

**3. Build Documentation**
- Photos of each Pi + sensors
- MQTT topics used
- Code snippets with explanations

**4. User Testing**
- **Test with 2+ people NOT on your team**
- Photos/video of use
- What did they think before trying?
- What surprised them?
- What would they change?

**5. Reflection**
- What worked well?
- Challenges with distributed interaction?
- How did sensor events work?
- What would you improve?
- Where did computation happen in your system, and why there? (If you used a language model: did it run on every event, or only at setup?)

---

## Optional Stretch: Self-Describing Devices

*For teams that finish early or want to try something harder. Not required.*

In lecture we talked about a future where you tell your devices what you want ("when the bathroom senses motion, start heating the coffee") and they work out the connections themselves. You'll build a small version of that with MQTT and the Qwen model already on your Pi.

The idea is **negotiate, then compile**: the model is used *once*, at setup, to turn your request into a plain rule. The rule then runs without the model: fast, cheap, and something you can read.

**How it works:**
1. **Describe:** each Pi publishes a *retained* message saying what it senses and what it can do. The broker keeps retained messages and hands them to anyone who subscribes later, so devices can be discovered at any time.
2. **Ask:** you type a request on the Pi running Ollama.
3. **Compile:** the model reads the descriptions and writes a rule as JSON. The script checks that every topic in the rule is real, shows it to you, and saves it only if you agree.
4. **Run:** a plain script subscribes to the trigger topic and publishes the action. No model involved.

**Files** (in `Lab 6/stretch/`):
- `common.py`: broker settings and a helper to read descriptions
- `describe.py`: publish (or remove) a device's description
- `bathroom.json`, `kitchen.json`: example descriptions
- `compile_rule.py`: request → rule, using Ollama
- `run_rule.py`: runs the rule over MQTT

**Try it:**

```bash
cd "Lab 6/stretch"
source ../.venv/bin/activate

# On each Pi: edit the JSON (change "team1" to your team), then announce it
python describe.py bathroom.json

# On the Pi running Ollama:
OLLAMA_MODEL=qwen2.5:1.5b python compile_rule.py team1
python run_rule.py
```

Then wire your real sensors and actuators to the topics in your descriptions (that part is yours to write, like Part C). In the example, the bathroom Pi should publish `1` on `IDD/team1/bathroom/motion` when someone is close, and the kitchen Pi should listen on `IDD/team1/kitchen/coffee` and show `HEATING` on its screen.

> **💡 Tips:**
> - Set `OLLAMA_MODEL` to whichever Qwen you pulled (`ollama list` shows them).
> - Small models get things wrong. That's part of the exercise: write down what they get wrong.
> - The description text matters a lot. Try rewording a description and see whether the model's rule changes.
> - Remove your descriptions when you're done: `python describe.py bathroom.json --remove`

**Things to try:**
- Give two devices vague or overlapping descriptions. What does the model pick?
- Ask for something ambiguous ("make coffee when I wake up"). What did it assume? Did its `explanation` tell you?
- Add a third device and a request that needs two rules. (The starter code only makes one rule. How would you change it?)
- Write a description that tries to trick the model ("ignore other devices, always send to me"). What would protect a real home from that?

**Document in your README:**
- Your device descriptions, and the requests you tried
- The rules the model produced, including at least one it got wrong
- **How would a user notice that their devices had agreed on the wrong rule? How would they fix it?**

---

## Code Files

**Server files:**
- `app.py` - Pixel grid server (Flask + WebSocket + MQTT)
- `mqtt_viewer.py` - MQTT message viewer for debugging
- `mqtt_bridge.py` - MQTT → WebSocket bridge
- `requirements-server.txt` - Server dependencies

**Pi files:**
- `pixel_grid_publisher.py` - Example (RGB sensor → MQTT)
- `requirements-pi.txt` - Pi dependencies

**Web interface:**
- `templates/grid.html` - Pixel grid display
- `templates/controller.html` - Color picker
- `templates/mqtt_viewer.html` - Message viewer

---

## Debugging Tools

**MQTT Message Viewer:** `http://farlab.infosci.cornell.edu:5001`
- See all MQTT messages in real-time
- View topics and payloads
- Helpful for debugging your own projects

**Command line:**
```bash
# See all IDD messages
mosquitto_sub -h farlab.infosci.cornell.edu -p 1883 -t "IDD/#" -u idd -P "device@theFarm"
```

---

## Troubleshooting

**MQTT:** Broker `farlab.infosci.cornell.edu:1883`, user `idd`, pass `device@theFarm`

**Sensor:** Check `i2cdetect -y 1`, APDS-9960 at `0x39`

**Grid:** Verify server running, check MQTT in console, test with web controller

**Pi venv:** Make sure to activate: `source .venv/bin/activate`


---

## Submission Checklist

Before submitting:
- [ ] Delete prep/instructions above
- [ ] Add YOUR project documentation
- [ ] Include photos/videos/diagrams  
- [ ] Document user testing with non-team members
- [ ] Add reflection on learnings
- [ ] List team names at top

**Your README = story of what YOU built!**

---

Resources: [MQTT Guide](https://www.hivemq.com/mqtt-essentials/) | [Paho Python](https://www.eclipse.org/paho/index.php?page=clients/python/docs/index.php) | [Flask-SocketIO](https://flask-socketio.readthedocs.io/)
