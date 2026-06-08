import { App } from "cdktf";
import { PersonalAssistantStack } from "./stacks/pa-stack";

const app = new App();
new PersonalAssistantStack(app, "pa-stack");
app.synth();
