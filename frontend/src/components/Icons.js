import React from 'react';

function Svg({ size = 18, children, ...props }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export const IconeEngrenagem = (props) => (
  <Svg {...props}>
    <circle cx="12" cy="12" r="3.1" />
    <path d="M19.2 13.6a7.4 7.4 0 0 0 0-3.2l1.9-1.4-1.9-3.3-2.2.9a7.6 7.6 0 0 0-2.7-1.6L14 2.9h-4l-.3 2.1a7.6 7.6 0 0 0-2.7 1.6l-2.2-.9-1.9 3.3 1.9 1.4a7.4 7.4 0 0 0 0 3.2l-1.9 1.4 1.9 3.3 2.2-.9a7.6 7.6 0 0 0 2.7 1.6l.3 2.1h4l.3-2.1a7.6 7.6 0 0 0 2.7-1.6l2.2.9 1.9-3.3z" />
  </Svg>
);

export const IconeSol = (props) => (
  <Svg {...props}>
    <circle cx="12" cy="12" r="4.2" />
    <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.2 5.2l1.4 1.4M17.4 17.4l1.4 1.4M18.8 5.2l-1.4 1.4M6.6 17.4l-1.4 1.4" />
  </Svg>
);

export const IconeLua = (props) => (
  <Svg {...props}>
    <path d="M20.5 14.2A8.6 8.6 0 0 1 9.8 3.5a8.6 8.6 0 1 0 10.7 10.7z" />
  </Svg>
);

export const IconeMenu = (props) => (
  <Svg {...props}>
    <path d="M4 6.5h16M4 12h16M4 17.5h16" />
  </Svg>
);

export const IconeFechar = (props) => (
  <Svg {...props}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Svg>
);

export const IconeMais = (props) => (
  <Svg {...props}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);

export const IconeSetaDireita = (props) => (
  <Svg {...props}>
    <path d="M5 12h13M12.5 6l6 6-6 6" />
  </Svg>
);

export const IconeSetaEsquerda = (props) => (
  <Svg {...props}>
    <path d="M19 12H6M11.5 18l-6-6 6-6" />
  </Svg>
);

export const IconeSpinner = (props) => (
  <Svg {...props}>
    <polyline points="21 3 21 9 15 9" />
    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L21 9" />
  </Svg>
);

export const IconeChevronBaixo = (props) => (
  <Svg {...props}>
    <path d="M6 9.5l6 6 6-6" />
  </Svg>
);

export const IconeChevronEsquerda = (props) => (
  <Svg {...props}>
    <path d="M14.5 6l-6 6 6 6" />
  </Svg>
);

export const IconeChevronDireita = (props) => (
  <Svg {...props}>
    <path d="M9.5 6l6 6-6 6" />
  </Svg>
);

export const IconeTelaCheia = (props) => (
  <Svg {...props}>
    <path d="M8.5 3.5h-5v5M15.5 3.5h5v5M20.5 15.5v5h-5M8.5 20.5h-5v-5" />
  </Svg>
);

export const IconeSairTelaCheia = (props) => (
  <Svg {...props}>
    <path d="M3.5 8.5h5v-5M20.5 8.5h-5v-5M15.5 20.5h5v-5M8.5 20.5h-5v-5" />
  </Svg>
);
