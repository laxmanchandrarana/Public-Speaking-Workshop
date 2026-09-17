import React from 'react';
import { motion } from 'framer-motion';
import { Shield, Compass, Sparkles } from 'lucide-react';

interface BenefitItem {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  accentGradient: string;
  borderColor: string;
}

const benefits: BenefitItem[] = [
  {
    id: 'confidence',
    title: 'Confidence',
    description: 'Build confidence when speaking in front of others.',
    icon: <Shield className="w-6 h-6 text-indigo-400" />,
    accentGradient: 'from-indigo-500/20 via-indigo-500/5 to-transparent',
    borderColor: 'group-hover:border-indigo-500/40',
  },
  {
    id: 'clarity',
    title: 'Clarity',
    description: 'Structure your thoughts and communicate clearly.',
    icon: <Compass className="w-6 h-6 text-purple-400" />,
    accentGradient: 'from-purple-500/20 via-purple-500/5 to-transparent',
    borderColor: 'group-hover:border-purple-500/40',
  },
  {
    id: 'impact',
    title: 'Impact',
    description: 'Make your message memorable.',
    icon: <Sparkles className="w-6 h-6 text-amber-400" />,
    accentGradient: 'from-amber-500/20 via-amber-500/5 to-transparent',
    borderColor: 'group-hover:border-amber-500/40',
  },
];

export const Benefits: React.FC = () => {
  return (
    <section className="py-20 sm:py-28 relative" aria-labelledby="benefits-heading">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="text-center max-w-2xl mx-auto mb-14 space-y-3">
          <span className="text-xs font-bold uppercase tracking-widest text-indigo-400">
            Why Attend
          </span>
          <h2
            id="benefits-heading"
            className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight"
          >
            Transform How You Speak
          </h2>
          <p className="text-base sm:text-lg text-gray-400">
            Master the core pillars of compelling presentation and genuine presence.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-8">
          {benefits.map((benefit, index) => (
            <motion.div
              key={benefit.id}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-50px' }}
              transition={{ duration: 0.5, delay: index * 0.1, ease: [0.16, 1, 0.3, 1] }}
              className={`group relative p-8 rounded-2xl bg-[#11131f]/70 border border-white/[0.08] ${benefit.borderColor} transition-all duration-300 hover:-translate-y-1 shadow-lg hover:shadow-2xl overflow-hidden`}
            >
              {/* Subtle top glow highlight */}
              <div
                className={`absolute inset-0 bg-gradient-to-b ${benefit.accentGradient} opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none`}
              />

              <div className="relative space-y-5">
                <div className="w-12 h-12 rounded-xl bg-white/[0.05] border border-white/10 flex items-center justify-center group-hover:scale-105 transition-transform duration-300">
                  {benefit.icon}
                </div>

                <div className="space-y-2">
                  <h3 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                    {benefit.title}
                  </h3>
                  <p className="text-sm sm:text-base text-gray-300/85 leading-relaxed">
                    {benefit.description}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};
