import { motion } from 'framer-motion';

import {Bot} from "lucide-react";

export const Overview = () => {
  return (
    <motion.div
      key="overview"
      className="max-w-3xl mx-auto md:mt-20"
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ delay: 0.5 }}
    >
      <div className="rounded-xl p-6 flex flex-col gap-4 leading-relaxed text-center max-w-xl">
        <div className='rounded-full border flex justify-center items-center size-20 mx-auto border-blue-500'><Bot className='mx-auto size-12' /></div>
        <p>
          Codex is an AI programming agent with access to up-to-date documentation of various tools (libraries, APIs, frameworks, etc.) and can search Stack Overflow for debugging assistance.
        </p>
      </div>
    </motion.div>
  );
};
