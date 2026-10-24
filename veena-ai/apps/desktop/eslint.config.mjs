import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "dist-electron", "release", "node_modules", "scripts/.*"] },
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}", "electron/**/*.ts"],
    plugins: { "react-hooks": reactHooks },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "no-restricted-syntax": [
        "error",
        { selector: "CallExpression[callee.name='eval']", message: "eval is not allowed" },
      ],
    },
  },
);
