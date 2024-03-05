import { TextEncoder, TextDecoder } from "node:util";

global.TextDecoder = TextDecoder;
global.TextEncoder = TextEncoder;
