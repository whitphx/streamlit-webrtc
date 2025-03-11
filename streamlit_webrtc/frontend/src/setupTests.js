import { TextEncoder, TextDecoder } from "node:util";
import '@testing-library/jest-dom';

global.TextDecoder = TextDecoder;
global.TextEncoder = TextEncoder;
