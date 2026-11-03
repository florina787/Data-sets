import { GraphE } from "../components/charts";
import { PageHeader } from "../components/ui";
export default function Tokens() {
  return <div><PageHeader title="Token Analytics" subtitle="Input, output and cached tokens, by agent and over time; local Qwen separated from paid inference with its real compute cost." /><GraphE full /></div>;
}
