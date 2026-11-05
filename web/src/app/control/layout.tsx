import "./control.css";
import { ControlFrame } from "./ControlFrame";

export const metadata = { title: "Operations" };

export default function ControlLayout({ children }: { children: React.ReactNode }) {
  return <ControlFrame>{children}</ControlFrame>;
}
