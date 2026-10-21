# Client brief: a small Kanban board

## The request
A client asks for a small local task board similar in broad purpose to Trello: "I need to organise work into To Do, In Progress and Done. I must be able to add cards with titles and descriptions, edit them, move them between columns, delete them, and still have my board after restarting the application."

Build a functioning web application from scratch. Do not copy Trello source code, brand assets, text, or distinctive visual design. Use your own simple layout and original CSS. This is a single-user, locally hosted prototype.

## Fixed product requirements
1. The home page is a usable HTML interface showing the three columns in this exact order: To Do (todo), In Progress (in_progress), Done (done).
2. A card has an ID, title, description, and column ID.
3. Create a card, edit its title/description, move it to a different column, and delete it.
4. Reject an empty/whitespace-only title and a column ID that is not one of the three allowed IDs. Return useful client errors rather than crashing.
5. Persist board state to a JSON data file whose path is supplied in BOARD_DATA_FILE; all cards must survive a process restart.
6. Use no paid API, network service, package installation, database server, user account system, or collaboration features. Python standard library plus browser HTML/CSS/JavaScript is sufficient.
7. The app must start with this command from its project directory:
   python app.py --host 127.0.0.1 --port PORT
   PORT is replaced with a free port chosen by the test runner.
8. Expose the exact API in API_CONTRACT.json. The controller's independent acceptance suite uses that contract.
9. Include a concise README.md with run instructions, data-file behavior, API summary, and known limitations.
10. Use the required interface IDs and card-action attributes from API_CONTRACT.json, so the interface is automatable.

## Working constraints
- Work only inside the files exposed by the agent's workspace tools.
- First submit a short implementation plan. Then inspect the starter, implement the application, test your own work, and finish with a factual summary.
- Do not say an unrun test passed. Keep the final response brief and list any known failures.
- You can use the provided tools to list/read/write project files and run only the named controlled checks. No arbitrary shell is available to the agent.
- All tool actions and model request/response text are captured by the external runner. This is an experimental trace, not a request to reveal hidden chain-of-thought.
