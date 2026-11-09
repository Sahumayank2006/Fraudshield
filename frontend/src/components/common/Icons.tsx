import React from "react";

interface IconProps {
  size?: number;
  className?: string;
  color?: string;
}

export const WordmarkMark: React.FC<IconProps> = ({ size = 20, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="2.5" y="2.5" width="15" height="15" stroke={color} strokeWidth="1.5" strokeLinecap="square" />
    <line x1="2.5" y1="17.5" x2="17.5" y2="2.5" stroke={color} strokeWidth="1.5" strokeLinecap="square" />
  </svg>
);

/* Accessible Decision Signal Shapes (Shape + Text + Color) */
export const SignalBlock: React.FC<IconProps> = ({ size = 12 }) => (
  <svg width={size} height={size} viewBox="0 0 12 12" fill="none" style={{ display: "inline-block", verticalAlign: "middle" }}>
    <rect x="1" y="1" width="10" height="10" fill="var(--block)" stroke="var(--block)" strokeWidth="1.5" strokeLinecap="square" />
  </svg>
);

export const SignalReview: React.FC<IconProps> = ({ size = 12 }) => (
  <svg width={size} height={size} viewBox="0 0 12 12" fill="none" style={{ display: "inline-block", verticalAlign: "middle" }}>
    <rect x="1" y="1" width="10" height="10" stroke="var(--review)" strokeWidth="1.5" strokeLinecap="square" />
    <path d="M1 1L11 11H1V1Z" fill="var(--review)" />
  </svg>
);

export const SignalApprove: React.FC<IconProps> = ({ size = 12 }) => (
  <svg width={size} height={size} viewBox="0 0 12 12" fill="none" style={{ display: "inline-block", verticalAlign: "middle" }}>
    <rect x="1" y="1" width="10" height="10" fill="none" stroke="var(--approve)" strokeWidth="1.5" strokeLinecap="square" />
  </svg>
);

export const IconPlay: React.FC<IconProps> = ({ size = 14, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
    <polygon points="4,2 14,8 4,14" fill={color} />
  </svg>
);

export const IconPause: React.FC<IconProps> = ({ size = 14, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
    <rect x="3" y="2" width="3.5" height="12" fill={color} />
    <rect x="9.5" y="2" width="3.5" height="12" fill={color} />
  </svg>
);

export const IconAttack: React.FC<IconProps> = ({ size = 14, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
    <path d="M8 1L10.5 6H15.5L11.5 9.5L13 15L8 11.5L3 15L4.5 9.5L0.5 6H5.5L8 1Z" stroke={color} strokeWidth="1.5" strokeLinecap="square" />
  </svg>
);

export const IconReset: React.FC<IconProps> = ({ size = 14, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
    <path d="M2 8A6 6 0 1 1 5 13.196" stroke={color} strokeWidth="1.5" strokeLinecap="square" />
    <polyline points="2 3 2 8 7 8" stroke={color} strokeWidth="1.5" strokeLinecap="square" />
  </svg>
);

export const IconDownload: React.FC<IconProps> = ({ size = 14, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
    <path d="M8 2V11M8 11L4 7M8 11L12 7M2 14H14" stroke={color} strokeWidth="1.5" strokeLinecap="square" />
  </svg>
);

export const IconCheck: React.FC<IconProps> = ({ size = 14, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
    <polyline points="2 8 6 12 14 3" stroke={color} strokeWidth="1.5" strokeLinecap="square" />
  </svg>
);

export const IconCross: React.FC<IconProps> = ({ size = 14, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
    <line x1="3" y1="3" x2="13" y2="13" stroke={color} strokeWidth="1.5" strokeLinecap="square" />
    <line x1="13" y1="3" x2="3" y2="13" stroke={color} strokeWidth="1.5" strokeLinecap="square" />
  </svg>
);
