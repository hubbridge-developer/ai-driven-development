import { Box, Typography } from '@mui/material';
import { BRAND } from '../theme';

/**
 * Enterprise brand lockup for the top-left of the app: a gradient badge holding
 * a custom "software + AI" glyph (code brackets around an AI spark), plus the
 * wordmark describing what the platform is.
 */
export default function BrandMark({
  showName = true,
  size = 40,
}: {
  showName?: boolean;
  size?: number;
}) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
      {/* Badge */}
      <Box
        sx={{
          position: 'relative',
          width: size,
          height: size,
          borderRadius: 2.5,
          background: BRAND.gradient,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 6px 16px rgba(13,148,136,0.35)',
          flexShrink: 0,
          // subtle inner highlight for depth (enterprise, not flat)
          '&::after': {
            content: '""',
            position: 'absolute',
            inset: 0,
            borderRadius: 'inherit',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.28)',
          },
        }}
      >
        <svg
          width="62%"
          height="62%"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          {/* code brackets */}
          <path
            d="M8.5 6.5 L3.5 12 L8.5 17.5"
            stroke="#fff"
            strokeWidth="1.9"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M15.5 6.5 L20.5 12 L15.5 17.5"
            stroke="#fff"
            strokeWidth="1.9"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* AI spark at the center */}
          <path
            d="M12 9 L12.75 11.25 L15 12 L12.75 12.75 L12 15 L11.25 12.75 L9 12 L11.25 11.25 Z"
            fill="#fff"
          />
        </svg>
      </Box>

      {showName && (
        <Box sx={{ lineHeight: 1.1 }}>
          <Typography
            component="span"
            sx={{
              fontWeight: 800,
              fontSize: 16,
              letterSpacing: '-0.02em',
              color: 'text.primary',
              display: 'block',
            }}
          >
            {BRAND.name}
          </Typography>
          <Typography
            component="span"
            sx={{
              fontSize: 10.5,
              fontWeight: 600,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'text.secondary',
              display: 'block',
              mt: '2px',
            }}
          >
            Software Delivery Platform
          </Typography>
        </Box>
      )}
    </Box>
  );
}
