import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
// Fuentes incluidas en la app (no se descargan de Google): se ven igual en la red de la Caja y sin internet.
import './styles/fuentes';
import './styles/index.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
